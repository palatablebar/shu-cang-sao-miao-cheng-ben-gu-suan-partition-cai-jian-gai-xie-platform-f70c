"""Enumerations shared by models, services and API schemas.

Keep in sync with frontend/src/constants/enums.ts (README §枚举出现位置).
"""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"          # 平台负责人：表元数据 / 预算阈值 / 基线
    ENGINEER = "engineer"    # 数据开发：提交 SQL 分析、申请改写
    VIEWER = "viewer"        # 财务 / BI：只读报告


class TableLayer(str, Enum):
    ODS = "ODS"
    DWD = "DWD"
    DWS = "DWS"
    ADS = "ADS"


class ParseStatus(str, Enum):
    PARSED = "parsed"
    UNPARSED = "unparsed"
    MISSING_TABLE = "missing_table"


class PruneBlockReason(str, Enum):
    NONE = "none"                                # 可裁剪
    FUNCTION_WRAPPED = "function_wrapped"        # 分区列被函数/表达式包裹
    IMPLICIT_CAST = "implicit_cast"              # 字面量类型与分区列不一致，隐式转换
    MISSING_PREDICATE = "missing_predicate"      # 完全没有分区谓词
    EXPRESSION_NOT_USABLE = "expression_not_usable"  # 分区列参与算术/coalesce 等
    TABLE_NOT_PARTITIONED = "table_not_partitioned"
    UNPARSED = "unparsed"
    MISSING_TABLE = "missing_table"


class AntiPattern(str, Enum):
    PARTITION_FUNCTION_WRAP = "partition_function_wrap"
    PARTITION_IMPLICIT_CAST = "partition_implicit_cast"
    SELECT_STAR = "select_star"
    MISSING_PARTITION_PREDICATE = "missing_partition_predicate"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class BudgetScope(str, Enum):
    GLOBAL = "global"
    LAYER = "layer"
    TABLE = "table"


class BudgetStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    OVER = "over"


class AuditAction(str, Enum):
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    QUERY_IMPORT = "query.import"
    QUERY_ANALYZE = "query.analyze"
    ESTIMATE_RUN = "estimate.run"
    REWRITE_GENERATE = "rewrite.generate"
    REWRITE_ADOPT = "rewrite.adopt"
    REWRITE_EXPORT = "rewrite.export"
    TABLE_UPDATE = "table.update"
    BUDGET_UPDATE = "budget.update"
    BUDGET_CREATE = "budget.create"
    FORBIDDEN = "auth.forbidden"
