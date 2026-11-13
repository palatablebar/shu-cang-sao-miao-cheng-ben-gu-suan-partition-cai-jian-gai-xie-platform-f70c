"""算法 2：反模式识别 → 等价改写 → 收益重估（重估复用算法 1，不猜数字）。

三类反模式
----------
1. ``partition_function_wrap``  分区列被 to_char/date/substr/cast 包裹  → 改写成裸列比较（低风险）
2. ``partition_implicit_cast``  分区列与整型/文本字面量隐式转换       → 改写成同类型字面量（低风险）
3. ``select_star``              投影为 *                              → 替换为表元数据登记的建议投影列（中风险）
4. ``missing_partition_predicate`` 无分区谓词                          → 补最近 N 天时间窗口（高风险）

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

from src.analysis.predicates import PartitionPredicate, build_predicate, split_and
from src.analysis.scoring import confidence_for, risk_level_for, score_of
from src.analysis.sql_analyzer import GIB, QueryAnalysis, TableProfile, analyze_query

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


def _resolve_profile(
    tree: exp.Expression, catalog: dict[str, TableProfile]
) -> tuple[exp.Table | None, TableProfile | None]:
    select = tree.find(exp.Select)
    if select is None:
        return None, None
    from_clause = select.args.get("from")
    source = getattr(from_clause, "this", None)
    if not isinstance(source, exp.Table):
        tables = list(tree.find_all(exp.Table))
        source = tables[0] if tables else None
    if not isinstance(source, exp.Table):
        return None, None
    return source, catalog.get((source.name or "").lower())


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


def _cmp(operator: str, column: str, value: str) -> exp.Expression:
    classes = {
        "=": exp.EQ,
        "!=": exp.NEQ,
        ">": exp.GT,
        ">=": exp.GTE,
        "<": exp.LT,
        "<=": exp.LTE,
    }
    cls = classes.get(operator, exp.EQ)
    return cls(this=exp.column(column), expression=exp.Literal.string(value))


def _unwrap_partition_predicate(predicate: PartitionPredicate, partition_key: str) -> exp.Expression | None:
    """Rebuild a bare-column predicate from a blocked (wrapped / cast) predicate."""
    value = (predicate.values or [None])[0]
    if value is None:
        return None
    kind = (predicate.wrapper_kind or "").lower()
    column = partition_key.lower()

    if kind == "implicit_integer_literal":
        if predicate.operator in ("between", "in"):
            if predicate.operator == "between" and len(predicate.values or []) >= 2:
                low = _normalize_date(predicate.values[0])
                high = _normalize_date(predicate.values[1])
                if not low or not high:
                    return None
                return exp.and_(_cmp(">=", column, low), _cmp("<=", column, high))
            options = [iso for iso in (_normalize_date(v) for v in (predicate.values or [])) if iso]
            if not options:
                return None
            return exp.Or(expressions=[_cmp("=", column, iso) for iso in options]) if len(options) > 1 else _cmp(
                "=", column, options[0]
            )
        iso = _normalize_date(value)
        return _cmp(predicate.operator, column, iso) if iso else None
    if kind == "implicit_text_literal":
        return None
    if kind in ("cast", "date_text", "date", "to_date", "to_char", "trunc", "date_trunc"):
        iso = _normalize_date(value)
        return _cmp(predicate.operator, column, iso) if iso else None
    if kind in ("month_part", "substr", "substring"):
        text = str(value)
        if re.fullmatch(r"\d{4}-\d{2}", text):
            start, end = _month_bounds(text)
            return exp.and_(_cmp(">=", column, start), _cmp("<", column, end))
        if re.fullmatch(r"\d{4}", text):
            year = int(text)
            return exp.and_(_cmp(">=", column, f"{year}-01-01"), _cmp("<", column, f"{year + 1}-01-01"))
        return None
    return None


def _window_predicate(profile: TableProfile, window_days: int) -> exp.Expression | None:
    current = profile.max_partition
    if not current:
        return None
    try:
        latest = date.fromisoformat(current)
    except ValueError:
        return None
    start = latest - timedelta(days=max(0, window_days - 1))
    return exp.GTE(this=exp.column(profile.partition_key.lower()), expression=exp.Literal.string(start.isoformat()))


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
    profile = catalog.get(before.target_table.lower())
    if profile is None or not profile.partitions:
        result.note = "目标表未登记分区元数据，无法生成分区裁剪改写"
        return result

    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except ParseError as exc:  # pragma: no cover - analyze_query already guarded
        result.note = f"sqlglot 解析失败：{exc}"
        return result

    select = tree.find(exp.Select)
    if select is None:
        result.note = "仅支持 SELECT 语句"
        return result

    partition_key = profile.partition_key
    where = select.args.get("where")
    conjuncts = split_and(where.this if where else None)
    predicates: list[PartitionPredicate] = []
    for conjunct in conjuncts:
        predicate = build_predicate(conjunct, partition_key.lower(), profile.partition_type)
        if predicate is not None:
            predicates.append(predicate)

    anti_patterns: list[str] = []
    fixes: list[str] = []

    for predicate in predicates:
        if predicate.usable:
            continue
        if predicate.reason in ("function_wrapped", "implicit_cast"):
            rebuilt = _unwrap_partition_predicate(predicate, partition_key)
            if rebuilt is None or predicate.node is None:
                continue
            original_sql = predicate.expression_sql
            predicate.node.replace(rebuilt)
            pattern = ANTI_FUNCTION if predicate.reason == "function_wrapped" else ANTI_CAST
            if pattern not in anti_patterns:
                anti_patterns.append(pattern)
            fixes.append(
                f"分区谓词 `{original_sql}` 改为裸列比较 `{rebuilt.sql(dialect='postgres')}`，恢复分区裁剪"
            )

    if before.blocked_reason == "missing_predicate":
        window = _window_predicate(profile, window_days)
        if window is not None:
            existing = select.args.get("where")
            combined = exp.and_(existing.this, window) if existing is not None else window
            select.set("where", exp.Where(this=combined))
            if ANTI_MISSING not in anti_patterns:
                anti_patterns.append(ANTI_MISSING)
            fixes.append(
                f"补分区时间窗口 `{window.sql(dialect='postgres')}`（最近 {window_days} 天，语义范围收窄 → 高风险）"
            )

    if _has_star(select) and profile.suggested_columns:
        available = [name for name in profile.suggested_columns if profile.column(name)]
        if available:
            select.set("expressions", [exp.column(name) for name in available])
            if ANTI_STAR not in anti_patterns:
                anti_patterns.append(ANTI_STAR)
            fixes.append(
                f"`SELECT *` 替换为 {len(available)} 个建议投影列（表元数据登记的下游消费列）"
            )

    if not anti_patterns:
        result.note = "未命中可改写的反模式（谓词与投影都合规）"
        return result

    rewritten_sql = tree.sql(dialect="postgres", pretty=True)

    # 收益重估：对改写后的 SQL 重新跑算法 1，而不是用系数猜。
    after = analyze_query(rewritten_sql, catalog)
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
    result.rewritable = result.saving_bytes > 0 and (result.saving_pct / 100) >= MIN_SAVING_RATIO
    result.rationale = (
        f"命中 {len(anti_patterns)} 类反模式；改写前扫描 {before.scan_bytes / GIB:.2f} GiB → "
        f"改写后 {after.scan_bytes / GIB:.2f} GiB，节省 {result.saving_pct:.1f}%；"
        f"风险 {result.risk_level}，置信度 {result.confidence:.2f}，"
        f"排序分 score = {result.saving_bytes} B × {result.confidence:.2f} ÷ 风险权重 = {result.score:.0f}"
    )
    return result
