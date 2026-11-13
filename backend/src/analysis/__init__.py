"""Pure-Python analysis core (no DB / no settings imports, unit-testable alone).

    sql_analyzer  -> 算法 1 解析 + 分区谓词分类 + 命中分区求值
    estimator     -> 算法 1 扫描字节 / 费用汇总
    rewriter      -> 算法 2 反模式识别 + 等价改写 + 收益重估
    scoring       -> 算法 2 风险权重 / 置信度 / 排序分数
"""
from src.analysis.estimator import EstimateRow, EstimateSummary, estimate_queries
from src.analysis.rewriter import RewriteResult, build_rewrite
from src.analysis.scoring import confidence_for, risk_level_for, score_of
from src.analysis.sql_analyzer import (
    ColumnProfile,
    QueryAnalysis,
    TableProfile,
    analyze_query,
)

__all__ = [
    "ColumnProfile",
    "TableProfile",
    "QueryAnalysis",
    "analyze_query",
    "EstimateRow",
    "EstimateSummary",
    "estimate_queries",
    "RewriteResult",
    "build_rewrite",
    "confidence_for",
    "risk_level_for",
    "score_of",
]
