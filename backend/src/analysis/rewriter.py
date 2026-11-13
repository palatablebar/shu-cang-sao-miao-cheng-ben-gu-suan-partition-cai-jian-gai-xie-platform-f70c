"""算法 2：反模式识别 → 等价改写 → 收益重估（重估复用算法 1，不猜数字）。

四类反模式
----------
1. ``partition_function_wrap``  分区列被 to_char/date/substr/cast 包裹  → 改写成裸列比较（低风险）
2. ``partition_implicit_cast``  分区列与整型/文本字面量隐式转换       → 改写成同类型字面量（低风险）
3. ``select_star``              投影为 *                              → 替换为表元数据登记的建议投影列（中风险）
4. ``missing_partition_predicate`` 无分区谓词                          → 补最近 N 天时间窗口（高风险）

多表口径
--------
联合查询逐表处理：每张表各自识别反模式、各自改写自己的分区谓词与投影，
**任何一张表无法确定等价改写（例如字面量无法解析成日期、建议投影列为空、补窗口没有分区依据）
就不生成建议**——不允许「改一半、省一半」的混合结果。所有谓词改写保留原表限定符
（``p.dt`` 改写后仍是 ``p.dt``），避免 JOIN 中列名歧义改变语义。

风险/置信度/排序见 ``src/analysis/scoring.py``；改写后的扫描字节由
``analyze_query`` 对改写文本重新求解得到，前端不参与任何估算。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.analysis.predicates import PartitionPredicate, build_predicate
from src.analysis.scoring import confidence_for, risk_level_for, score_of
from src.analysis.sql_analyzer import (
    GIB,
    QueryAnalysis,
    SourceRef,
    TableProfile,
    analyze_query,
    attribute_predicates,
    resolve_sources,
    star_sources,
)

ANTI_FUNCTION = "partition_function_wrap"
ANTI_CAST = "partition_implicit_cast"
ANTI_STAR = "select_star"
ANTI_MISSING = "missing_partition_predicate"

MIN_SAVING_RATIO = 0.05


@dataclass
class RewriteResult:
    rewritable: bool = False
    rewritten_sql: str = ""
    anti_patterns: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    confidence: float = 0.0
    before: QueryAnalysis | None = None
    after: QueryAnalysis | None = None
    before_scan_bytes: int = 0
    after_scan_bytes: int = 0
    saving_bytes: int = 0
    saving_cost_cny: float = 0.0
    saving_pct: float = 0.0
    score: float = 0.0
    fixes: list[str] = field(default_factory=list)
    rationale: str = ""
    note: str = ""
    # 逐表改写结果：改写前后都按表给出扫描字节 / 命中分区 / 裁剪原因，供前端展开对照。
    table_changes: list[dict] = field(default_factory=list)


def _resolve_profile(
    tree: exp.Expression, catalog: dict[str, TableProfile]
) -> tuple[exp.Table | None, TableProfile | None]:
    """Compatibility helper: first physical source only (see ``resolve_sources`` for joins)."""
    sources, _ = resolve_sources(tree, catalog)
    if not sources:
        return None, None
    return sources[0].node, sources[0].profile


def _has_star(select: exp.Select) -> bool:
    for projection in select.expressions:
        if isinstance(projection, exp.Star):
            return True
        if isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
            return True
    return False


def _normalize_date(value: str) -> str | None:
    text = str(value).strip().strip("'")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{8}", text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
        return text.replace("/", "-")
    return None


def _month_bounds(month: str) -> tuple[str, str]:
    year, mon = int(month[:4]), int(month[5:7])
    start = date(year, mon, 1)
    end = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1)
    return start.isoformat(), end.isoformat()


def _column_expr(column: str, qualifier: str) -> exp.Expression:
    """Build a column reference that keeps the source table qualifier (``p.dt`` stays ``p.dt``)."""
    return exp.column(column, table=qualifier) if qualifier else exp.column(column)


def _cmp(operator: str, column: str, value: str, qualifier: str = "") -> exp.Expression:
    classes = {
        "=": exp.EQ,
        "!=": exp.NEQ,
        ">": exp.GT,
        ">=": exp.GTE,
        "<": exp.LT,
        "<=": exp.LTE,
    }
    cls = classes.get(operator, exp.EQ)
    return cls(this=_column_expr(column, qualifier), expression=exp.Literal.string(value))


def _rebuild_connector(
    predicate: PartitionPredicate, partition_key: str, qualifier: str
) -> exp.Expression | None:
    """Rebuild ``dt = 20261110 OR dt = 20261111`` branch by branch (rewriter only)."""
    node = predicate.node
    if node is None or not isinstance(node, (exp.And, exp.Or)):
        return None
    branches = node.flatten()
    rebuilt: list[exp.Expression] = []
    for branch in branches:
        part = build_predicate(branch, partition_key, "date_str")
        if part is None:
            return None
        if part.usable:
            rebuilt.append(branch.copy())
            continue
        if part.reason not in ("function_wrapped", "implicit_cast"):
            return None
        piece = _unwrap_partition_predicate(part, partition_key, qualifier)
        if piece is None:
            return None
        rebuilt.append(piece)
    if not rebuilt:
        return None
    # 每个分支都必须是「可裁剪」或「能等价还原」的分区谓词；只要有一个分支不是分区谓词
    # （_rebuild_connector 已返回 None），就不会走到这里，避免改掉混在 OR 里的业务条件。
    if len(rebuilt) == 1:
        return rebuilt[0]
    builder = exp.and_ if isinstance(node, exp.And) else exp.or_
    return builder(*rebuilt)


def _unwrap_partition_predicate(
    predicate: PartitionPredicate, partition_key: str, qualifier: str = ""
) -> exp.Expression | None:
    """Rebuild a bare-column predicate from a blocked (wrapped / cast) predicate."""
    value = (predicate.values or [None])[0]
    if value is None:
        return None
    kind = (predicate.wrapper_kind or "").lower()
    column = partition_key.lower()

    if predicate.node is not None and isinstance(predicate.node, (exp.And, exp.Or)):
        return _rebuild_connector(predicate, partition_key, qualifier)

    if kind == "implicit_integer_literal":
        if predicate.operator in ("between", "in"):
            if predicate.operator == "between" and len(predicate.values or []) >= 2:
                low = _normalize_date(predicate.values[0])
                high = _normalize_date(predicate.values[1])
                if not low or not high:
                    return None
                return exp.and_(
                    _cmp(">=", column, low, qualifier), _cmp("<=", column, high, qualifier)
                )
            options = [iso for iso in (_normalize_date(v) for v in (predicate.values or [])) if iso]
            if not options:
                return None
            return (
                exp.or_(*[_cmp("=", column, iso, qualifier) for iso in options])
                if len(options) > 1
                else _cmp("=", column, options[0], qualifier)
            )
        iso = _normalize_date(value)
        return _cmp(predicate.operator, column, iso, qualifier) if iso else None
    if kind == "implicit_text_literal":
        return None
    if kind in ("cast", "date_text", "date", "to_date", "to_char", "trunc", "date_trunc"):
        iso = _normalize_date(value)
        return _cmp(predicate.operator, column, iso, qualifier) if iso else None
    if kind in ("month_part", "substr", "substring"):
        text = str(value)
        if re.fullmatch(r"\d{4}-\d{2}", text):
            start, end = _month_bounds(text)
            return exp.and_(
                _cmp(">=", column, start, qualifier), _cmp("<", column, end, qualifier)
            )
        if re.fullmatch(r"\d{4}", text):
            year = int(text)
            return exp.and_(
                _cmp(">=", column, f"{year}-01-01", qualifier),
                _cmp("<", column, f"{year + 1}-01-01", qualifier),
            )
        return None
    return None


def _window_predicate(profile: TableProfile, window_days: int, qualifier: str = "") -> exp.Expression | None:
    current = profile.max_partition
    if not current:
        return None
    try:
        latest = date.fromisoformat(current)
    except ValueError:
        return None
    start = latest - timedelta(days=max(0, window_days - 1))
    return exp.GTE(
        this=_column_expr(profile.partition_key.lower(), qualifier),
        expression=exp.Literal.string(start.isoformat()),
    )


def _rewrite_select_star(
    select: exp.Select, source: SourceRef, sources: list[SourceRef], global_star: bool
) -> exp.Expression | None:
    """Replace a ``*`` projection for one table with its suggested columns (keeps JOINs intact)."""
    profile = source.profile
    if profile is None:
        return None
    available = [name for name in profile.suggested_columns if profile.column(name)]
    if not available:
        return None
    # 单表查询保持裸列名；联合查询带别名，避免同名列歧义。
    qualifier = source.alias if len(sources) > 1 else ""
    replacements = [_column_expr(name, qualifier) for name in available]

    if not global_star:
        if not isinstance(select, exp.Select):
            return None
        expressions: list[exp.Expression] = []
        changed = False
        for projection in select.expressions:
            if isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
                qualifier = (projection.table or "").lower()
                if qualifier and any(
                    qualifier in {
                        candidate.alias.lower(),
                        candidate.name.lower(),
                        (candidate.node.alias_or_name or "").lower(),
                        (candidate.profile.qualified.lower() if candidate.profile else ""),
                    }
                    for candidate in sources
                    if candidate is source
                ):
                    expressions.extend(replacements)
                    changed = True
                    continue
            expressions.append(projection)
        if not changed:
            return None
        return exp.Select(expressions=expressions)

    # 未限定 ``*``：联合查询里无法把 * 拆给多张表，等价改写不可确定 → 不生成建议。
    if len(sources) > 1:
        return None
    select.set("expressions", replacements)
    return select


def _analyze_table_sources(sql: str, catalog: dict[str, TableProfile]):
    """Parse once and expose per-source nodes used by the rewrite path."""
    tree = sqlglot.parse_one(sql, read="postgres")
    sources, unsupported = resolve_sources(tree, catalog)
    if unsupported is not None or not sources:
        return tree, sources, unsupported
    return tree, sources, None


def build_rewrite(
    sql: str,
    catalog: dict[str, TableProfile],
    window_days: int = 7,
    cost_per_gib_cny: float = 0.30,
    risk_weights: dict[str, float] | None = None,
) -> RewriteResult:
    """Detect anti-patterns, produce an equivalent rewrite and re-estimate it."""
    before = analyze_query(sql, catalog)
    result = RewriteResult(before=before, before_scan_bytes=before.scan_bytes)
    if before.parse_status != "parsed":
        result.note = before.rationale or "SQL 解析失败，无法生成改写"
        return result
    if not before.target_table:
        result.note = "未识别到目标表，无法生成改写"
        return result
    if not before.tables:
        result.note = "未识别到可估算的表，无法生成改写"
        return result

    try:
        tree, sources, unsupported = _analyze_table_sources(sql, catalog)
    except ParseError as exc:  # pragma: no cover - analyze_query already guarded
        result.note = f"sqlglot 解析失败：{exc}"
        return result
    if unsupported is not None or not sources:
        result.note = unsupported or "未识别到目标表，无法生成改写"
        return result

    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        result.note = "仅支持 SELECT 语句"
        return result

    global_star, star_aliases = star_sources(select, sources)
    predicate_nodes, _ambiguous = attribute_predicates(select, sources)

    anti_patterns: list[str] = []
    fixes: list[str] = []
    blocked_tables: list[str] = []
    pending_windows: list[tuple[SourceRef, str]] = []

    for index, source in enumerate(sources):
        profile = source.profile
        if profile is None or not profile.partitions:
            blocked_tables.append(f"{source.name}（元数据缺失，无法确定等价改写）")
            continue
        # 单表查询保持原来的 `dt = ...` 写法；联合查询必须保留限定符，否则 JOIN 中同名列会改到别的表。
        qualifier = source.alias if len(sources) > 1 else ""
        table_patterns: list[str] = []
        table_fixes: list[str] = []

        # --- 1. 分区谓词反模式（逐表） ---
        for node in predicate_nodes.get(index, []):
            predicate = build_predicate(node, profile.partition_key.lower(), profile.partition_type)
            if predicate is None or predicate.usable:
                continue
            if predicate.reason not in ("function_wrapped", "implicit_cast"):
                continue
            rebuilt = _unwrap_partition_predicate(predicate, profile.partition_key, qualifier)
            if rebuilt is None or predicate.node is None:
                blocked_tables.append(
                    f"{source.name}（谓词 `{predicate.expression_sql}` 无法等价改写为裸列比较）"
                )
                continue
            original_sql = predicate.expression_sql
            predicate.node.replace(rebuilt)
            pattern = ANTI_FUNCTION if predicate.reason == "function_wrapped" else ANTI_CAST
            if pattern not in table_patterns:
                table_patterns.append(pattern)
            table_fixes.append(
                f"[{source.name}] 分区谓词 `{original_sql}` 改为裸列比较 "
                f"`{rebuilt.sql(dialect='postgres')}`，恢复分区裁剪"
            )

        # sources 与 before.tables 一一对应（自连接的两个别名必须按位置匹配，不能按表名）。
        table_row = before.tables[index] if index < len(before.tables) else None
        if table_row is not None and table_row["blocked_reason"] == "missing_predicate":
            pending_windows.append((source, qualifier))

        # --- 2. SELECT *（逐表） ---
        if (global_star or source.alias in star_aliases) and profile.suggested_columns:
            replacement = _rewrite_select_star(select, source, sources, global_star)
            if replacement is None:
                if len(sources) > 1 and global_star:
                    blocked_tables.append(
                        f"{source.name}（`SELECT *` 同时覆盖多张表，无法拆成保留其它表的等价投影）"
                    )
                else:
                    blocked_tables.append(f"{source.name}（建议投影列为空，无法替换 `*`）")
            else:
                if isinstance(replacement, exp.Select) and not global_star:
                    # 多表限定 star：把重建后的投影写回原 select。
                    select.set("expressions", replacement.expressions)
                    if source.alias in star_aliases:
                        star_aliases.discard(source.alias)
                if ANTI_STAR not in table_patterns:
                    table_patterns.append(ANTI_STAR)
                table_fixes.append(
                    f"[{source.name}] `SELECT *` 替换为 "
                    f"{len([n for n in profile.suggested_columns if profile.column(n)])} 个建议投影列"
                    f"（表元数据登记的下游消费列）"
                )

        if table_patterns:
            for pattern in table_patterns:
                if pattern not in anti_patterns:
                    anti_patterns.append(pattern)
            fixes.extend(table_fixes)

    # --- 3. 缺分区谓词：补时间窗口（逐表） ---
    # 放在谓词改写之后统一处理：谓词改写是原地 .replace()，若中途重建 Where 节点，
    # 先前替换的谓词会与语法树脱钩，改写结果丢失（改写后仍表现为隐式转换）。
    for source, qualifier in pending_windows:
        profile = source.profile
        window = _window_predicate(profile, window_days, qualifier) if profile else None
        if window is None:
            blocked_tables.append(f"{source.name}（缺少分区边界，无法补时间窗口）")
            continue
        where_clause = select.args.get("where")
        if where_clause is not None and isinstance(where_clause.this, exp.Expression):
            where_clause.set("this", exp.and_(where_clause.this, window))
        else:
            select.set("where", exp.Where(this=window))
        pattern = ANTI_MISSING
        if pattern not in anti_patterns:
            anti_patterns.append(pattern)
        fixes.append(
            f"[{source.name}] 补分区时间窗口 `{window.sql(dialect='postgres')}`"
            f"（最近 {window_days} 天，语义范围收窄 → 高风险）"
        )

    if blocked_tables:
        # 任一张表无法确定等价改写 → 整条查询不生成建议（不允许局部改写后混着全表扫描）。
        result.note = "以下表无法确定等价改写，未生成建议：" + "；".join(blocked_tables)
        result.anti_patterns = sorted(anti_patterns)
        result.fixes = fixes
        return result

    if not anti_patterns:
        result.note = "未命中可改写的反模式（谓词与投影都合规）"
        return result

    rewritten_sql = tree.sql(dialect="postgres", pretty=True)

    # 收益重估：对改写后的 SQL 重新跑算法 1，而不是用系数猜。
    after = analyze_query(rewritten_sql, catalog)
    if after.parse_status != "parsed":
        result.note = f"改写后的 SQL 无法重新解析：{after.parse_error or after.rationale}"
        result.anti_patterns = sorted(anti_patterns)
        result.fixes = fixes
        return result

    result.after = after
    result.rewritten_sql = rewritten_sql
    result.anti_patterns = sorted(anti_patterns)
    result.risk_level = risk_level_for(result.anti_patterns)
    result.confidence = confidence_for(result.anti_patterns)
    result.after_scan_bytes = after.scan_bytes
    result.saving_bytes = max(0, before.scan_bytes - after.scan_bytes)
    result.saving_pct = round(result.saving_bytes / max(before.scan_bytes, 1) * 100, 2)
    result.saving_cost_cny = round(result.saving_bytes / GIB * float(cost_per_gib_cny), 6)
    result.score = score_of(result.saving_bytes, result.confidence, result.risk_level, risk_weights)
    result.fixes = fixes
    result.table_changes = _table_changes(before, after)
    result.rewritable = result.saving_bytes > 0 and (result.saving_pct / 100) >= MIN_SAVING_RATIO
    result.rationale = (
        f"命中 {len(anti_patterns)} 类反模式（{len(before.tables)} 张表逐表改写）；"
        f"改写前扫描 {before.scan_bytes / GIB:.2f} GiB → "
        f"改写后 {after.scan_bytes / GIB:.2f} GiB，节省 {result.saving_pct:.1f}%；"
        f"风险 {result.risk_level}，置信度 {result.confidence:.2f}，"
        f"排序分 score = {result.saving_bytes} B × {result.confidence:.2f} ÷ 风险权重 = {result.score:.0f}"
    )
    return result


def _table_changes(before: QueryAnalysis, after: QueryAnalysis) -> list[dict]:
    """Pair before/after per-table rows (by position, so self-joins keep their aliases apart)."""
    changes: list[dict] = []
    for index, row in enumerate(before.tables):
        after_row = after.tables[index] if index < len(after.tables) else {}
        changes.append(
            {
                "table_name": row["table_name"],
                "alias": row.get("alias", ""),
                "after_alias": after_row.get("alias", ""),
                "before_scan_bytes": row["scan_bytes"],
                "after_scan_bytes": after_row.get("scan_bytes", 0),
                "before_hit_partition_count": row["hit_partition_count"],
                "after_hit_partition_count": after_row.get("hit_partition_count", 0),
                "before_total_partition_count": row["total_partition_count"],
                "after_total_partition_count": after_row.get("total_partition_count", 0),
                "before_prunable": row["prunable"],
                "after_prunable": after_row.get("prunable", False),
                "before_blocked_reason": row["blocked_reason"],
                "after_blocked_reason": after_row.get("blocked_reason", "none"),
                "changed": row["scan_bytes"] != after_row.get("scan_bytes", 0),
            }
        )
    return changes
