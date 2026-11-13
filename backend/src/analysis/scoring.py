"""算法 2 的风险/置信度/排序口径（README §算法 2）。

排序分数：``score = saving_bytes × confidence ÷ risk_weight``
    * 低风险改写（去掉函数包裹，语义完全等价）      risk_weight = 1.0, confidence = 0.95
    * 中风险改写（SELECT * → 建议投影列）           risk_weight = 1.6, confidence = 0.90
    * 高风险改写（补时间窗口，语义范围收窄）         risk_weight = 2.4, confidence = 0.62
同一查询命中多类反模式时取最严风险 + 最低置信度（保守口径）。
"""
from __future__ import annotations

RISK_WEIGHTS: dict[str, float] = {"low": 1.0, "medium": 1.6, "high": 2.4}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

CONFIDENCE_BY_PATTERN: dict[str, float] = {
    "partition_function_wrap": 0.95,
    "partition_implicit_cast": 0.95,
    "select_star": 0.90,
    "missing_partition_predicate": 0.62,
}

RISK_BY_PATTERN: dict[str, str] = {
    "partition_function_wrap": "low",
    "partition_implicit_cast": "low",
    "select_star": "medium",
    "missing_partition_predicate": "high",
}


def risk_weight(level: str, weights: dict[str, float] | None = None) -> float:
    table = weights or RISK_WEIGHTS
    return float(table.get(level, table.get("high", 2.4)))


def risk_level_for(anti_patterns: list[str]) -> str:
    worst = "low"
    for pattern in anti_patterns:
        level = RISK_BY_PATTERN.get(pattern, "medium")
        if RISK_ORDER[level] > RISK_ORDER[worst]:
            worst = level
    return worst


def confidence_for(anti_patterns: list[str]) -> float:
    if not anti_patterns:
        return 0.0
    return min(CONFIDENCE_BY_PATTERN.get(p, 0.5) for p in anti_patterns)


def score_of(
    saving_bytes: int,
    confidence: float,
    risk_level: str,
    weights: dict[str, float] | None = None,
) -> float:
    return round(max(0.0, float(saving_bytes)) * float(confidence) / risk_weight(risk_level, weights), 3)
