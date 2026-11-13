"""算法 1：SQL 解析 → 分区谓词可用性 → 命中分区求值 → 扫描字节估算。

输入 / 输出契约
----------------
输入 : 一条 PostgreSQL 方言 SQL + 表画像（分区清单 / 列字节 / 建议投影列）
输出 : ``QueryAnalysis``（可解释：分区谓词、命中分区、不可裁剪原因、列裁剪比例、扫描字节）

多表口径（JOIN / 逗号连接）
--------------------------
一条查询可以同时扫描多张表（例如订单归因同时扫 ``dwd_order_detail`` 与
``dwd_payment_flow``）。算法逐表独立求解，再汇总：

    scan_bytes(query) = Σ_{t ∈ 查询引用表} scan_bytes(t)
    scan_bytes(t)     = Σ_{p ∈ P_hit(t)} bytes_p × col_ratio(t)

* 每张表有独立的分区谓词判定、命中分区与裁剪原因（``tables[t]``）；
* 列引用按限定符归属到表；无限定符且多张表都有同名列时，按「保守放大」计入所有候选表
  （列裁剪比例只会被高估，不会低估扫描量）；
* 无限定符的分区列同时可能属于多张表时判为 ``ambiguous_predicate``，不用于裁剪；
* 任何一张表不在元数据目录里，整条查询显式返回 ``missing_table``（扫描量记 0，不静默部分估算），
  但仍会列出已解析表的明细，便于定位缺口。

公式
----
    col_ratio(t)  = Σ_{c ∈ 引用列(t)且 c 不是分区键} bytes_c / Σ_{c ∈ 数据列(t)} bytes_c
    scan_bytes(t) = Σ_{p ∈ P_hit(t)} bytes_p × col_ratio(t)
    P_hit(t)      = { p | 分区谓词在 p.dt 上求值为真 }，裁剪失效时 P_hit(t) = 全部分区

失败态
------
    unparsed        sqlglot 解析失败 / 查询形态超出支持范围（前端展示原始 SQL + 失败原因，不计入扫描量）
    missing_table   至少一张目标表不在元数据目录里
    其余失败一律降级为「不可裁剪」并给出 blocked_reason，绝不静默按 0 计。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.analysis.predicates import (
    BLOCK_AMBIGUOUS,
    BLOCK_EXPRESSION,
    PartitionPredicate,
    build_predicate,
    partition_filter,
    split_and,
)

GIB = 1024 ** 3
# count(*) 只读 parquet footer + 最小列；给一个保守下限比例而不是 0。
COUNT_STAR_RATIO = 0.03

UNSUPPORTED_SCOPE_MESSAGE = "仅支持 FROM/JOIN 直接引用物理表（不支持子查询 / CTE / 集合运算）"


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
class SourceRef:
    """One physical table occurrence in FROM/JOIN (self-joins keep separate aliases)."""

    node: exp.Table
    alias: str
    name: str
    profile: TableProfile | None


@dataclass
class TableAnalysis:
    """算法 1 的单表结果（多表查询逐表拆解，扫描量可对账）。"""

    table_name: str
    qualified_name: str = ""
    alias: str = ""
    status: str = "analyzed"          # analyzed / missing_table / not_partitioned
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
    counted_in_total: bool = True
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


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
    # --- 多表拆解（单表查询同样有一行，前端按表展开即可） ---
    tables: list[dict] = field(default_factory=list)
    table_count: int = 0
    table_scan_sum_bytes: int = 0
    reconciliation: dict = field(default_factory=dict)

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


def star_sources(select: exp.Select, sources: list[SourceRef]) -> tuple[bool, set[str]]:
    """Return (unqualified star present, {aliases explicitly projected with t.*})."""
    global_star = False
    qualified: set[str] = set()
    for projection in select.expressions:
        if isinstance(projection, exp.Star):
            global_star = True
        elif isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
            qualifier = (projection.table or "").lower()
            for source in sources:
                if qualifier and _qualifier_matches(qualifier, source):
                    qualified.add(source.alias)
    return global_star, qualified


def _qualifier_matches(qualifier: str, source: SourceRef) -> bool:
    lowered = qualifier.lower()
    candidates = {source.alias.lower(), source.name.lower(), (source.node.alias_or_name or "").lower()}
    if source.profile is not None:
        candidates.add(source.profile.qualified.lower())
    return lowered in candidates


def resolve_sources(tree: exp.Expression, catalog: dict[str, TableProfile]) -> tuple[list[SourceRef] | None, str | None]:
    """Collect every direct FROM/JOIN source; reject shapes we cannot attribute safely."""
    if not isinstance(tree, exp.Select):
        return None, "仅支持单条 SELECT 语句（当前为其他语句类型）"
    if any(isinstance(node, (exp.Subquery, exp.Union, exp.CTE)) for node in tree.walk()):
        return None, UNSUPPORTED_SCOPE_MESSAGE

    from_clause = tree.args.get("from_") or tree.args.get("from")
    if from_clause is None:
        return None, UNSUPPORTED_SCOPE_MESSAGE
    nodes: list[exp.Expression] = [from_clause.this]
    for join in tree.args.get("joins") or []:
        nodes.append(join.this)
    if any(not isinstance(node, exp.Table) for node in nodes):
        return None, UNSUPPORTED_SCOPE_MESSAGE

    sources: list[SourceRef] = []
    for node in nodes:
        name = (node.name or "").lower()
        alias = (node.alias_or_name or name or "").lower()
        sources.append(SourceRef(node=node, alias=alias, name=name, profile=catalog.get(name)))
    return sources, None


def _source_for_qualified(column: exp.Column, sources: list[SourceRef]) -> list[SourceRef]:
    """Which sources a column reference could belong to (conservative on ambiguity)."""
    qualifier = (column.table or "").lower()
    if qualifier:
        return [source for source in sources if _qualifier_matches(qualifier, source)]
    name = (column.name or "").lower()
    holders = [source for source in sources if source.profile and source.profile.column(name)]
    return holders


def _column_belongs_to(column: exp.Column, source: SourceRef, sources: list[SourceRef]) -> bool:
    qualifier = (column.table or "").lower()
    if qualifier:
        return _qualifier_matches(qualifier, source)
    name = (column.name or "").lower()
    candidates = [s for s in sources if s.profile and s.profile.column(name)]
    if candidates:
        return source in candidates
    # 元数据里查不到该列（例如投影别名）：不归入任何真实表，避免虚增列裁剪比例。
    return False


def _collect_references(tree: exp.Expression, source: SourceRef, sources: list[SourceRef]) -> list[str]:
    names: list[str] = []
    for column in tree.find_all(exp.Column):
        if isinstance(column.this, exp.Star):
            continue
        if not _column_belongs_to(column, source, sources):
            continue
        name = (column.name or "").lower()
        if name and name not in names:
            names.append(name)
    return names


def attribute_predicates(
    select: exp.Select,
    sources: list[SourceRef],
) -> tuple[dict[int, list[exp.Expression]], dict[int, list[exp.Expression]]]:
    """Split WHERE conjuncts per source; conjuncts spanning sources become ambiguous.

    Returns ``(predicate_nodes_by_source, ambiguous_nodes_by_source)``.
    """
    where = select.args.get("where")
    conjuncts = split_and(where.this if where else None)
    predicate_nodes: dict[int, list[exp.Expression]] = {}
    ambiguous_nodes: dict[int, list[exp.Expression]] = {}
    for conjunct in conjuncts:
        touched: dict[int, list[exp.Column]] = {}
        for column in conjunct.find_all(exp.Column):
            if isinstance(column.this, exp.Star):
                continue
            name = (column.name or "").lower()
            for index, source in enumerate(sources):
                profile = source.profile
                if profile is None or not profile.partitions:
                    continue
                if name != profile.partition_key.lower():
                    continue
                if _column_belongs_to(column, source, sources):
                    touched.setdefault(index, []).append(column)
        if not touched:
            continue
        if len(touched) == 1:
            predicate_nodes.setdefault(next(iter(touched)), []).append(conjunct)
        else:
            # 同一谓词同时引用多张表的分区列（含无限定符且多表都有 dt）：归属不明，不参与裁剪。
            for index in touched:
                ambiguous_nodes.setdefault(index, []).append(conjunct)
    return predicate_nodes, ambiguous_nodes


def _analyze_source(
    source: SourceRef,
    sources: list[SourceRef],
    tree: exp.Expression,
    select: exp.Select,
    predicate_nodes: list[exp.Expression],
    ambiguous_nodes: list[exp.Expression],
    global_star: bool,
    star_aliases: set[str],
) -> TableAnalysis:
    profile = source.profile
    base = dict(table_name=source.name, alias=source.alias)
    if profile is None:
        return TableAnalysis(
            **base,
            status="missing_table",
            prunable=False,
            blocked_reason="missing_table",
            counted_in_total=False,
            rationale=f"目标表 {source.name} 不在元数据目录中，无法估算该表扫描量",
        )
    if not profile.partitions:
        return TableAnalysis(
            **base,
            qualified_name=profile.qualified,
            status="not_partitioned",
            partition_key=profile.partition_key,
            prunable=False,
            blocked_reason="table_not_partitioned",
            has_star=global_star or source.alias in star_aliases,
            full_scan_bytes=profile.total_bytes,
            scan_bytes=profile.total_bytes,
            rationale=f"{profile.table_name} 未登记分区，退化为整表扫描 {_fmt_gib(profile.total_bytes)}",
        )

    partition_key = profile.partition_key.lower()
    predicates: list[PartitionPredicate] = []
    for node in predicate_nodes:
        predicate = build_predicate(node, partition_key, profile.partition_type)
        if predicate is not None:
            predicates.append(predicate)
    for node in ambiguous_nodes:
        predicates.append(
            PartitionPredicate(
                expression_sql=node.sql(dialect="postgres"),
                operator="expr",
                literal_sql="-",
                usable=False,
                reason=BLOCK_AMBIGUOUS,
                node=node,
            )
        )

    usable = [p for p in predicates if p.usable and p.evaluator is not None]
    blocked = [p for p in predicates if not p.usable]

    has_star = global_star or source.alias in star_aliases
    references = _collect_references(tree, source, sources)
    data_referenced = [
        name for name in references if name != partition_key and profile.column(name)
    ]

    if has_star:
        projected = [c.name for c in profile.data_columns]
        col_ratio = 1.0
        ratio_note = "SELECT *（全列）"
    elif data_referenced:
        projected = data_referenced
        col_ratio = min(
            1.0,
            sum(profile.column(name).bytes for name in data_referenced) / max(profile.data_bytes, 1),
        )
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
            "table": source.name,
            "table_alias": source.alias,
            "expression": p.expression_sql,
            "operator": p.operator,
            "literal": p.literal_sql,
            "usable": p.usable,
            "reason": p.reason,
            "wrapper_kind": p.wrapper_kind,
        }
        for p in predicates
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
            "ambiguous_predicate": "分区列归属不明（多表同名列）",
            "missing_predicate": "缺少分区谓词",
        }.get(blocked_reason, blocked_reason)
        rationale = (
            f"{profile.table_name}（{len(profile.partitions)} 个日分区）{reason_text} → 裁剪失效，"
            f"命中全部 {len(hit)} 个分区（{_fmt_gib(hit_bytes)}）× 列裁剪比例 {col_ratio:.2f}"
            f"（{ratio_note}）= {_fmt_gib(scan_bytes)}"
        )

    return TableAnalysis(
        **base,
        qualified_name=profile.qualified,
        status="analyzed",
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


def _aggregate(tables: list[TableAnalysis], sources: list[SourceRef]) -> QueryAnalysis:
    """Fold per-table results into the query-level contract (sum is explicit for reconciliation)."""
    primary = sources[0]
    known = [row for row in tables if row.status != "missing_table"]
    missing = [row for row in tables if row.status == "missing_table"]
    table_scan_sum = sum(row.scan_bytes for row in known)
    table_hit_bytes = sum(row.hit_bytes for row in known)
    table_hit_count = sum(row.hit_partition_count for row in known)
    table_partition_count = sum(row.total_partition_count for row in known)
    table_full_scan = sum(row.full_scan_bytes for row in known)

    multi = len(tables) > 1
    # 多表查询的谓词在表级已经拆分；查询级保留一份带 table 字段的扁平列表，UI 以表级为准。
    flat_predicates: list[dict] = []
    for row in tables:
        flat_predicates.extend(row.predicates)

    blocked_rows = [row for row in tables if not row.prunable and row.status != "missing_table"]
    if missing:
        status = "missing_table"
        blocked_reason = "missing_table"
        blocked_expression = None
        prunable = False
        scan_bytes = 0
        hit_bytes = 0
        hit_count = 0
        full_scan_bytes = 0
    else:
        status = "parsed"
        blocked_reason = next(
            (row.blocked_reason for row in blocked_rows if row.blocked_reason != "none"),
            "none" if not blocked_rows else "missing_predicate",
        )
        blocked_expression = next(
            (row.blocked_expression for row in blocked_rows if row.blocked_expression), None
        )
        prunable = all(row.prunable for row in tables)
        scan_bytes = table_scan_sum
        hit_bytes = table_hit_bytes
        hit_count = table_hit_count
        full_scan_bytes = table_full_scan

    hit_partitions: list[str] = []
    if not multi:
        hit_partitions = list(tables[0].hit_partitions) if tables else []

    col_ratio: float
    if not multi:
        col_ratio = tables[0].col_ratio if tables else 1.0
    else:
        col_ratio = round(scan_bytes / hit_bytes, 6) if hit_bytes else 1.0

    if status != "parsed":
        if missing:
            rationale = (
                f"查询引用 {len(tables)} 张表，其中 {len(missing)} 张不在元数据目录（"
                + "、".join(row.table_name for row in missing)
                + "），整条查询无法估算；已解析表的明细仅用于定位缺口"
            )
        else:
            rationale = "查询无法估算"
    elif not multi:
        rationale = tables[0].rationale if tables else ""
    else:
        parts = [f"{row.table_name} {_fmt_gib(row.scan_bytes)}" for row in tables]
        if prunable:
            rationale = (
                f"联合查询 {len(tables)} 张表："
                + "；".join(parts)
                + f"；合计 {_fmt_gib(scan_bytes)}（表级明细之和与查询总量对账一致）"
            )
        else:
            reasons = "、".join(
                f"{row.table_name}={row.blocked_reason}"
                for row in blocked_rows
                if row.blocked_reason != "none"
            )
            rationale = (
                f"联合查询 {len(tables)} 张表，裁剪在 {len(blocked_rows)} 张表上失效（{reasons}）："
                + "；".join(parts)
                + f"；合计 {_fmt_gib(scan_bytes)}（表级明细之和与查询总量对账一致）"
            )

    counted_tables = [row for row in tables if row.counted_in_total] if status == "parsed" else []
    counted_sum = sum(row.scan_bytes for row in counted_tables)
    return QueryAnalysis(
        parsed=True,
        parse_status=status,
        target_table=primary.name,
        partition_key=known[0].partition_key if known else None,
        prunable=prunable,
        blocked_reason=blocked_reason,
        blocked_expression=blocked_expression,
        predicates=flat_predicates,
        hit_partitions=hit_partitions,
        hit_partition_count=hit_count,
        total_partition_count=table_partition_count,
        hit_bytes=hit_bytes,
        col_ratio=col_ratio,
        projected_columns=[name for row in tables for name in row.projected_columns],
        referenced_columns=[name for row in tables for name in row.referenced_columns],
        has_star=any(row.has_star for row in tables),
        scan_bytes=scan_bytes,
        full_scan_bytes=full_scan_bytes,
        rationale=rationale,
        tables=[row.to_dict() for row in tables],
        table_count=len(tables),
        table_scan_sum_bytes=counted_sum,
        reconciliation={
            "query_scan_bytes": scan_bytes,
            "table_scan_sum_bytes": counted_sum,
            "delta_bytes": scan_bytes - counted_sum,
            "balanced": status == "parsed" and scan_bytes == counted_sum,
            "missing_table_count": len(missing),
        },
    )


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

    sources, unsupported = resolve_sources(tree, catalog)
    if unsupported is not None:
        return QueryAnalysis(
            parsed=False,
            parse_status="unparsed",
            parse_error=unsupported[:400],
            blocked_reason="unparsed",
            rationale=unsupported,
        )
    if not sources:
        return QueryAnalysis(
            parsed=True,
            parse_status="missing_table",
            blocked_reason="missing_table",
            rationale="未识别到目标表，无法估算扫描量",
        )

    select = tree
    global_star, star_aliases = star_sources(select, sources)
    predicate_nodes, ambiguous_nodes = attribute_predicates(select, sources)

    tables = [
        _analyze_source(
            source,
            sources,
            tree,
            select,
            predicate_nodes.get(index, []),
            ambiguous_nodes.get(index, []),
            global_star,
            star_aliases,
        )
        for index, source in enumerate(sources)
    ]
    return _aggregate(tables, sources)


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
