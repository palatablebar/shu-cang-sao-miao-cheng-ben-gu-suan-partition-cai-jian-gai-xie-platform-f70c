"""RewriteSuggestion schemas."""
from pydantic import BaseModel

from src.schemas.query import ReconciliationOut, TableAnalysisOut


class RewriteGenerateRequest(BaseModel):
    query_id: int | None = None
    limit: int = 12


class TableRewriteChangeOut(BaseModel):
    """改写前后逐表对照：扫描字节 / 命中分区 / 裁剪原因。"""

    table_name: str
    alias: str = ""
    after_alias: str = ""
    before_scan_bytes: int = 0
    after_scan_bytes: int = 0
    before_hit_partition_count: int = 0
    after_hit_partition_count: int = 0
    before_total_partition_count: int = 0
    after_total_partition_count: int = 0
    before_prunable: bool = False
    after_prunable: bool = False
    before_blocked_reason: str = "none"
    after_blocked_reason: str = "none"
    changed: bool = False


class RewriteOut(BaseModel):
    id: int
    suggestion_no: str
    query_log_id: int
    query_external_id: str
    query_title: str
    target_table: str | None
    anti_patterns: list[str]
    risk_level: str
    confidence: float
    before_scan_bytes: int
    after_scan_bytes: int
    saving_bytes: int
    saving_cost_cny: float
    saving_pct: float
    score: float
    status: str
    rationale: str
    table_count: int = 0
    table_changes: list[TableRewriteChangeOut] = []


class RewriteDetail(RewriteOut):
    original_sql: str
    rewritten_sql: str
    fixes: list[str]
    before_rationale: str
    after_rationale: str
    after_prunable: bool
    after_hit_partition_count: int
    after_total_partition_count: int
    before_tables: list[TableAnalysisOut] = []
    after_tables: list[TableAnalysisOut] = []
    before_reconciliation: ReconciliationOut | None = None
    after_reconciliation: ReconciliationOut | None = None
    qualified: bool = True
    rejection_reason: str = ""


class RewriteReevaluateOut(BaseModel):
    suggestion_no: str
    before_scan_bytes: int
    after_scan_bytes: int
    saving_bytes: int
    saving_pct: float
    saving_cost_cny: float
    monthly_saving_cny: float
    after_prunable: bool
    after_hit_partition_count: int
    after_total_partition_count: int
    rationale: str
    table_changes: list[TableRewriteChangeOut] = []
