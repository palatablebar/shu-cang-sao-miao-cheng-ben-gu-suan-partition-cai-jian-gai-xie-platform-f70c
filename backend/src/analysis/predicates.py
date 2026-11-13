"""Partition-predicate extraction, usability classification and evaluation.

算法 1 的判定规则（README §算法 1）：
    * 裸列比较（``dt = '2026-11-12'`` / ``dt BETWEEN ..`` / ``dt IN (..)``）= 可裁剪
    * 分区列被函数或表达式包裹（``to_char(dt,..)`` / ``date(dt)`` / ``dt::date`` / ``substr(dt,1,7)``
      / ``coalesce(dt,..)``）= 不可裁剪
    * 字面量类型与分区列类型不一致（date_str 列比整型字面量）= 隐式转换，不可裁剪
    * 完全没有分区谓词 = 不可裁剪
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlglot import exp

COMPARISONS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)

OPERATOR_LABEL = {
    exp.EQ: "=",
    exp.NEQ: "!=",
    exp.GT: ">",
    exp.GTE: ">=",
    exp.LT: "<",
    exp.LTE: "<=",
}

FLIP = {"=": "=", "!=": "!=", ">": "<", ">=": "<=", "<": ">", "<=": ">="}

BLOCK_FUNCTION = "function_wrapped"
BLOCK_CAST = "implicit_cast"
BLOCK_EXPRESSION = "expression_not_usable"


@dataclass
class PartitionPredicate:
    """One conjunct of the WHERE clause that touches the partition column."""

    expression_sql: str
    operator: str
    literal_sql: str
    usable: bool
    reason: str = "ok"
    wrapper_kind: str | None = None   # to_char / date / cast / substr / coalesce / arithmetic
    values: list[str] | None = None
    evaluator: Callable[[str], bool] | None = None
    node: exp.Expression | None = None   # AST node (rewriter mutates it; never serialized)

    @property
    def summary(self) -> str:
        if self.usable:
            return f"{self.operator} {self.literal_sql}（裸列比较，可裁剪）"
        return f"{self.reason}（{self.expression_sql}）"


def split_and(node: exp.Expression | None) -> list[exp.Expression]:
    """Flatten a top-level conjunction into its conjuncts."""
    if node is None:
        return []
    if isinstance(node, exp.Paren):
        return split_and(node.this)
    if isinstance(node, exp.And):
        return split_and(node.this) + split_and(node.expression)
    return [node]


def _literal_value(node: exp.Expression | None) -> tuple[str, str] | None:
    """Return (python-agnostic sql text, kind) for a literal node, else None."""
    if node is None:
        return None
    if isinstance(node, exp.Literal):
        kind = "int" if node.is_int else "float" if node.is_number else "str"
        return (node.this, kind)
    if isinstance(node, exp.Neg):
        inner = _literal_value(node.this)
        if inner and inner[1] in ("int", "float"):
            return (f"-{inner[0]}", inner[1])
    if isinstance(node, exp.Cast):
        inner = _literal_value(node.this)
        if inner:
            return inner
    return None


# sqlglot 把 to_char / date / substr 解析成具体节点类，统一映射成改写器能识别的语义类别。
_WRAPPER_CLASS = {
    "time_to_str": "date_text",
    "to_char": "date_text",
    "date": "date_text",
    "to_date": "date_text",
    "date_str_to_date": "date_text",
    "trunc": "date_text",
    "date_trunc": "date_text",
    "cast": "cast",
    "substring": "month_part",
    "substr": "month_part",
}


def _wrapper_kind(pk_column: exp.Column, stop_at: exp.Expression) -> str | None:
    """Walk from the partition column up to the comparison node and describe the wrapper."""
    node: exp.Expression | None = pk_column
    seen: str | None = None
    while node is not None and node is not stop_at:
        parent = node.parent
        if isinstance(parent, exp.Cast):
            seen = "cast"
        elif isinstance(parent, exp.Func):
            raw = (parent.sql_name() or type(parent).__name__ or "").lower()
            seen = _WRAPPER_CLASS.get(raw, raw or "function")
        elif isinstance(parent, (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod, exp.Coalesce, exp.If)):
            seen = seen or "expression"
        node = parent
    return seen


def _pk_columns(node: exp.Expression, pk_name: str) -> list[exp.Column]:
    return [c for c in node.find_all(exp.Column) if (c.name or "").lower() == pk_name]


def _classify_comparison(
    node: exp.Expression, pk_name: str, pk_type: str
) -> PartitionPredicate | None:
    """Classify one comparison node that references the partition column."""
    expression_sql = node.sql(dialect="postgres")
    if isinstance(node, exp.Between):
        bare = node.this
        low = _literal_value(node.args.get("low"))
        high = _literal_value(node.args.get("high"))
        if isinstance(bare, exp.Column) and (bare.name or "").lower() == pk_name:
            if low is None or high is None:
                return PartitionPredicate(expression_sql, "between", "-", False, BLOCK_EXPRESSION)
            if pk_type == "date_str" and "int" in (low[1], high[1]):
                return PartitionPredicate(
                    expression_sql,
                    "between",
                    f"{low[0]}..{high[0]}",
                    False,
                    BLOCK_CAST,
                    wrapper_kind="implicit_integer_literal",
                    values=[low[0], high[0]],
                )
            lo, hi = low[0], high[0]
            return PartitionPredicate(
                expression_sql,
                "between",
                f"{lo}..{hi}",
                True,
                "ok",
                values=[lo, hi],
                evaluator=lambda value, lo=lo, hi=hi: lo <= value <= hi,
            )
        wrapper = _wrapper_kind(bare, node) if isinstance(bare, exp.Expression) else None
        return PartitionPredicate(
            expression_sql,
            "between",
            "-",
            False,
            BLOCK_FUNCTION if wrapper else BLOCK_EXPRESSION,
            wrapper_kind=wrapper,
        )

    if isinstance(node, exp.In):
        bare = node.this
        options = node.args.get("expressions") or []
        if isinstance(bare, exp.Column) and (bare.name or "").lower() == pk_name:
            values = [_literal_value(o) for o in options]
            if not values or any(v is None for v in values):
                return PartitionPredicate(expression_sql, "in", "-", False, BLOCK_EXPRESSION)
            if pk_type == "date_str" and any(v[1] in ("int", "float") for v in values if v):
                return PartitionPredicate(
                    expression_sql,
                    "in",
                    "-",
                    False,
                    BLOCK_CAST,
                    wrapper_kind="implicit_integer_literal",
                    values=[v[0] for v in values if v],
                )
            text = ", ".join(v[0] for v in values if v)
            allowed = {v[0] for v in values if v}
            return PartitionPredicate(
                expression_sql,
                "in",
                text,
                True,
                "ok",
                values=sorted(allowed),
                evaluator=lambda value, allowed=allowed: value in allowed,
            )
        wrapper = _wrapper_kind(bare, node) if isinstance(bare, exp.Expression) else None
        return PartitionPredicate(
            expression_sql,
            "in",
            "-",
            False,
            BLOCK_FUNCTION if wrapper else BLOCK_EXPRESSION,
            wrapper_kind=wrapper,
        )

    label = OPERATOR_LABEL.get(type(node))
    if label is None:
        return None
    left = node.this
    right = node.expression

    left_is_pk = isinstance(left, exp.Column) and (left.name or "").lower() == pk_name
    right_is_pk = isinstance(right, exp.Column) and (right.name or "").lower() == pk_name

    if left_is_pk:
        literal = _literal_value(right)
        bare, other, operator = left, right, label
    elif right_is_pk:
        literal = _literal_value(left)
        bare, other, operator = right, left, FLIP[label]
    else:
        wrapper = _wrapper_kind(_pk_columns(node, pk_name)[0], node) if _pk_columns(node, pk_name) else None
        other_literal = _literal_value(left) or _literal_value(right)
        return PartitionPredicate(
            expression_sql,
            label,
            other_literal[0] if other_literal else "-",
            False,
            BLOCK_FUNCTION if wrapper else BLOCK_EXPRESSION,
            wrapper_kind=wrapper or ("implicit_integer_literal" if other_literal and other_literal[1] != "str" else None),
            values=[other_literal[0]] if other_literal else None,
        )

    if literal is None:
        return PartitionPredicate(
            expression_sql, operator, other.sql(dialect="postgres"), False, BLOCK_EXPRESSION
        )
    value, kind = literal
    if pk_type == "date_str" and kind in ("int", "float"):
        return PartitionPredicate(
            expression_sql,
            operator,
            value,
            False,
            BLOCK_CAST,
            wrapper_kind="implicit_integer_literal",
            values=[value],
        )
    if pk_type == "int" and kind == "str":
        return PartitionPredicate(
            expression_sql, operator, value, False, BLOCK_CAST, wrapper_kind="implicit_text_literal", values=[value]
        )
    return PartitionPredicate(
        expression_sql,
        operator,
        value,
        True,
        "ok",
        values=[value],
        evaluator=lambda partition_value, op=operator, v=value: _compare(op, v, partition_value),
    )


def _comparison_nodes(node: exp.Expression) -> list[exp.Expression]:
    found: list[exp.Expression] = []
    for candidate in node.walk():
        if isinstance(candidate, COMPARISONS) or isinstance(candidate, (exp.Between, exp.In)):
            found.append(candidate)
    return found


def _build_predicate_impl(
    node: exp.Expression, pk_name: str, pk_type: str
) -> PartitionPredicate | None:
    """Classify one WHERE conjunct; returns None when it does not touch the partition column."""
    if not _pk_columns(node, pk_name):
        return None

    # AND/OR composite of partition-only comparisons -> evaluate recursively.
    if isinstance(node, exp.Paren):
        inner = build_predicate(node.this, pk_name, pk_type)
        return inner
    if isinstance(node, exp.And):
        parts = [build_predicate(c, pk_name, pk_type) for c in node.flatten()]
        return _merge_parts(node, parts, "and")
    if isinstance(node, exp.Or):
        parts = [build_predicate(c, pk_name, pk_type) for c in node.flatten()]
        return _merge_parts(node, parts, "or")

    if isinstance(node, COMPARISONS) or isinstance(node, (exp.Between, exp.In)):
        return _classify_comparison(node, pk_name, pk_type)

    # partition column buried in a non-comparison expression (e.g. coalesce(dt,..) IS NULL)
    pk_column = _pk_columns(node, pk_name)[0]
    wrapper = _wrapper_kind(pk_column, node)
    return PartitionPredicate(
        node.sql(dialect="postgres"),
        "expr",
        "-",
        False,
        BLOCK_FUNCTION if wrapper else BLOCK_EXPRESSION,
        wrapper_kind=wrapper,
    )


def _merge_parts(
    node: exp.Expression, parts: list[PartitionPredicate | None], joiner: str
) -> PartitionPredicate:
    expression_sql = node.sql(dialect="postgres")
    if joiner == "and":
        usable = all(p is not None and p.usable for p in parts)
    else:
        usable = any(p is not None and p.usable for p in parts)
    if usable:
        values: list[str] = []
        evaluators = []
        for part in parts:
            if part and part.values:
                values.extend(part.values)
            if part and part.usable and part.evaluator is not None:
                evaluators.append(part.evaluator)
        if joiner == "and":
            evaluator = lambda value: all(fn(value) for fn in evaluators)  # noqa: E731
        else:
            evaluator = lambda value: any(fn(value) for fn in evaluators)  # noqa: E731
        return PartitionPredicate(
            expression_sql, joiner, f"({len(parts)} 分支)", True, "ok", values=values, evaluator=evaluator
        )
    blockers = [p for p in parts if p is not None and not p.usable]
    first = blockers[0] if blockers else None
    return PartitionPredicate(
        expression_sql,
        joiner,
        "-",
        False,
        first.reason if first else BLOCK_EXPRESSION,
        wrapper_kind=first.wrapper_kind if first else None,
    )


def _compare(op: str, value: str, partition_value: str) -> bool:
    if op == "in":
        return partition_value == value
    try:
        left, right = str(partition_value), str(value)
        if op == "=":
            return left == right
        if op == "!=":
            return left != right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
    except TypeError:  # pragma: no cover - defensive
        return False
    return False


def partition_filter(predicate: PartitionPredicate) -> Callable[[str], bool] | None:
    """Turn a usable predicate into a predicate over partition values."""
    if not predicate.usable:
        return None
    return predicate.evaluator


def build_predicate(
    node: exp.Expression, pk_name: str, pk_type: str
) -> PartitionPredicate | None:
    """Public wrapper: classify a WHERE conjunct and keep the AST node for rewriting."""
    result = _build_predicate_impl(node, pk_name, pk_type)
    if result is not None:
        result.node = node
    return result
