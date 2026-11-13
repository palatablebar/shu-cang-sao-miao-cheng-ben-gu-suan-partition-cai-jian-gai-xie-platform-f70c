"""算法 1：SQL 解析 → 分区谓词可用性 → 命中分区求值 → 扫描字节估算。

输入 / 输出契约
----------------
输入 : 一条 PostgreSQL 方言 SQL + 表画像（分区清单 / 列字节 / 建议投影列）
输出 : ``QueryAnalysis``（可解释：分区谓词、命中分区、不可裁剪原因、列裁剪比例、扫描字节）

公式
----
    col_ratio  = Σ_{c ∈ 引用列且 c 不是分区键} bytes_c / Σ_{c ∈ 数据列} bytes_c
    scan_bytes = Σ_{p ∈ P_hit} bytes_p × col_ratio
    P_hit      = { p | 分区谓词在 p.dt 上求值为真 }，裁剪失效时 P_hit = 全部分区

失败态
------
    unparsed        sqlglot 解析失败（前端展示原始 SQL + 失败原因，不计入扫描量）
    missing_table   目标表不在元数据目录里
    其余失败一律降级为「不可裁剪」并给出 blocked_reason，绝不静默按 0 计。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.analysis.predicates import (
    BLOCK_EXPRESSION,
    PartitionPredicate,
    build_predicate,
    partition_filter,
    split_and,
)

GIB = 1024 ** 3
# count(*) 只读 parquet footer + 最小列；给一个保守下限比例而不是 0。
COUNT_STAR_RATIO = 0.03


@dataclass
class ColumnProfile:
    name: str
    data_type: str = "string"
    bytes: int = 0
    is_partition_key: bool = False
    note: str = ""


@dataclass
class TableProfile:
    schema_name: str
    table_name: str
    partition_key: str
    partition_type: str = "date_str"
    partitions: list[tuple[str, int]] = field(default_factory=list)
    columns: list[ColumnProfile] = field(default_factory=list)
    suggested_columns: list[str] = field(default_factory=list)
    total_bytes: int = 0

    @property
    def qualified(self) -> str:
        return f"{self.schema_name}.{self.table_name}"

    @property
    def data_columns(self) -> list[ColumnProfile]:
        return [c for c in self.columns if not c.is_partition_key]

    @property
    def data_bytes(self) -> int:
        explicit = sum(c.bytes for c in self.data_columns)
        return explicit or self.total_bytes

    @property
    def max_partition(self) -> str | None:
        return max((dt for dt, _ in self.partitions), default=None)

    def column(self, name: str) -> ColumnProfile | None:
        lowered = name.lower()
        for col in self.columns:
            if col.name.lower() == lowered:
                return col
        return None


@dataclass
class QueryAnalysis:
    parsed: bool = True
    parse_status: str = "parsed"
    parse_error: str | None = None
    target_table: str | None = None
    partition_key: str | None = None
    prunable: bool = False
    blocked_reason: str = "none"
    blocked_expression: str | None = None
    predicates: list[dict] = field(default_factory=list)
    hit_partitions: list[str] = field(default_factory=list)
    hit_partition_count: int = 0
    total_partition_count: int = 0
    hit_bytes: int = 0
    col_ratio: float = 1.0
    projected_columns: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)
    has_star: bool = False
    scan_bytes: int = 0
    full_scan_bytes: int = 0
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _fmt_gib(value: int | float | None) -> str:
    return f"{float(value or 0) / GIB:.2f} GiB"


def _star_projection(select: exp.Select) -> bool:
    for projection in select.expressions:
        if isinstance(projection, exp.Star):
            return True
        if isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
            return True
    return False


def _resolve_table(tree: exp.Expression, catalog: dict[str, TableProfile]) -> tuple[exp.Table | None, TableProfile | None]:
    select = tree.find(exp.Select)
    if select is None:
        return None, None
    from_clause = select.args.get("from")
    source = getattr(from_clause, "this", None)
    if not isinstance(source, exp.Table):
        # 子查询 / 值表函数：不是我们覆盖的查询形态
        candidates = [t for t in tree.find_all(exp.Table)]
        source = candidates[0] if candidates else None
    if not isinstance(source, exp.Table):
        return None, None
    name = (source.name or "").lower()
    profile = catalog.get(name)
    return source, profile


def _column_belongs_to(column: exp.Column, table: exp.Table, profile: TableProfile) -> bool:
    qualifier = (column.table or "").lower()
    if not qualifier:
        return True
    return qualifier in {
        (table.alias_or_name or "").lower(),
        profile.table_name.lower(),
        profile.qualified.lower(),
    }


def _collect_references(tree: exp.Expression, table: exp.Table, profile: TableProfile) -> list[str]:
    names: list[str] = []
    for column in tree.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            continue
        if not _column_belongs_to(column, table, profile):
            continue
        name = (column.name or "").lower()
        if name and name not in names:
            names.append(name)
    return names


def analyze_query(sql: str, catalog: dict[str, TableProfile]) -> QueryAnalysis:
    """把一条 SQL 变成可解释的扫描量估算结果（纯函数，不碰数据库）。"""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except ParseError as exc:
        return QueryAnalysis(
            parsed=False,
            parse_status="unparsed",
            parse_error=str(exc).splitlines()[0][:400],
            blocked_reason="unparsed",
            rationale=f"sqlglot 解析失败：{str(exc).splitlines()[0][:200]}",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return QueryAnalysis(
            parsed=False,
            parse_status="unparsed",
            parse_error=f"{type(exc).__name__}: {exc}"[:400],
            blocked_reason="unparsed",
            rationale="sqlglot 解析失败（未知错误）",
        )

    select = tree.find(exp.Select)
    if select is None:
        return QueryAnalysis(
            parsed=False,
            parse_status="unparsed",
            parse_error="not a select statement",
            blocked_reason="unparsed",
            rationale="仅支持 SELECT 语句（当前为其他语句类型）",
        )

    table_node, profile = _resolve_table(tree, catalog)
    table_name = (table_node.name or "").lower() if table_node else None
    if profile is None:
        return QueryAnalysis(
            parsed=True,
            parse_status="missing_table",
            target_table=table_name,
            blocked_reason="missing_table",
            rationale=f"目标表 {table_name or '<未知>'} 不在元数据目录中，无法估算扫描量",
        )

    if not profile.partitions:
        return QueryAnalysis(
            parsed=True,
            parse_status="parsed",
            target_table=profile.table_name,
            partition_key=profile.partition_key,
            prunable=False,
            blocked_reason="table_not_partitioned",
            total_partition_count=0,
            has_star=_star_projection(select),
            full_scan_bytes=profile.total_bytes,
            scan_bytes=profile.total_bytes,
            rationale=f"{profile.table_name} 未登记分区，退化为整表扫描 {_fmt_gib(profile.total_bytes)}",
        )

    where = select.args.get("where")
    conjuncts = split_and(where.this if where else None)
    predicate_list: list[PartitionPredicate] = []
    for conjunct in conjuncts:
        predicate = build_predicate(conjunct, profile.partition_key.lower(), profile.partition_type)
        if predicate is not None:
            predicate_list.append(predicate)

    usable = [p for p in predicate_list if p.usable and p.evaluator is not None]
    blocked = [p for p in predicate_list if not p.usable]

    has_star = _star_projection(select)
    references = _collect_references(tree, table_node, profile)
    partition_key = profile.partition_key.lower()
    data_referenced = [n for n in references if n != partition_key and profile.column(n)]

    if has_star:
        projected = [c.name for c in profile.data_columns]
        col_ratio = 1.0
        ratio_note = "SELECT *（全列）"
    elif data_referenced:
        projected = data_referenced
        col_ratio = min(1.0, sum(profile.column(n).bytes for n in data_referenced) / max(profile.data_bytes, 1))
        ratio_note = f"引用 {len(data_referenced)}/{len(profile.data_columns)} 列"
    else:
        projected = []
        col_ratio = COUNT_STAR_RATIO
        ratio_note = "仅聚合/计数，按最小列比例"

    if usable:
        filters = [partition_filter(p) for p in usable]
        hit = [dt for dt, _ in profile.partitions if all(fn(dt) for fn in filters if fn)]
        prunable = True
        blocked_reason = "none"
        blocked_expression = None
    else:
        hit = [dt for dt, _ in profile.partitions]
        prunable = False
        if blocked:
            first = blocked[0]
            blocked_reason = first.reason
            blocked_expression = first.expression_sql
        else:
            blocked_reason = "missing_predicate"
            blocked_expression = None

    bytes_by_dt = dict(profile.partitions)
    hit_bytes = sum(bytes_by_dt.get(dt, 0) for dt in hit)
    scan_bytes = int(round(hit_bytes * col_ratio))

    predicates_payload = [
        {
            "expression": p.expression_sql,
            "operator": p.operator,
            "literal": p.literal_sql,
            "usable": p.usable,
            "reason": p.reason,
            "wrapper_kind": p.wrapper_kind,
        }
        for p in predicate_list
    ]

    if prunable:
        rationale = (
            f"{profile.table_name}（{len(profile.partitions)} 个日分区）分区谓词为裸列比较 → "
            f"命中 {len(hit)} 个分区（{_fmt_gib(hit_bytes)}）× 列裁剪比例 {col_ratio:.2f}（{ratio_note}）= "
            f"{_fmt_gib(scan_bytes)}"
        )
    else:
        reason_text = {
            "function_wrapped": "分区列被函数包裹",
            "implicit_cast": "分区列与字面量类型不一致（隐式转换）",
            "expression_not_usable": "分区列参与复杂表达式",
            "missing_predicate": "缺少分区谓词",
        }.get(blocked_reason, blocked_reason)
        rationale = (
            f"{profile.table_name}（{len(profile.partitions)} 个日分区）{reason_text} → 裁剪失效，"
            f"命中全部 {len(hit)} 个分区（{_fmt_gib(hit_bytes)}）× 列裁剪比例 {col_ratio:.2f}"
            f"（{ratio_note}）= {_fmt_gib(scan_bytes)}"
        )

    return QueryAnalysis(
        parsed=True,
        parse_status="parsed",
        target_table=profile.table_name,
        partition_key=profile.partition_key,
        prunable=prunable,
        blocked_reason=blocked_reason,
        blocked_expression=blocked_expression,
        predicates=predicates_payload,
        hit_partitions=hit,
        hit_partition_count=len(hit),
        total_partition_count=len(profile.partitions),
        hit_bytes=hit_bytes,
        col_ratio=round(col_ratio, 6),
        projected_columns=projected,
        referenced_columns=references,
        has_star=has_star,
        scan_bytes=scan_bytes,
        full_scan_bytes=profile.total_bytes,
        rationale=rationale,
    )


def catalog_from_tables(tables) -> dict[str, TableProfile]:
    """Adapt ORM ``TableMeta`` rows into the pure-Python catalog used above."""

    def build(table) -> TableProfile:
        columns = [
            ColumnProfile(
                name=c.name,
                data_type=c.data_type,
                bytes=c.bytes,
                is_partition_key=c.is_partition_key,
                note=c.note or "",
            )
            for c in table.columns
        ]
        return TableProfile(
            schema_name=table.schema_name,
            table_name=table.table_name,
            partition_key=table.partition_key,
            partition_type=table.partition_type,
            partitions=[(p.dt, p.bytes) for p in table.partitions],
            columns=columns,
            suggested_columns=list(table.suggested_columns or []),
            total_bytes=table.total_bytes,
        )

    return {table.table_name.lower(): build(table) for table in tables}
