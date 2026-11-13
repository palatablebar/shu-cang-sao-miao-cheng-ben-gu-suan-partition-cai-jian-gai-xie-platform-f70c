"""RewriteSuggestion schemas."""
from pydantic import BaseModel


class RewriteGenerateRequest(BaseModel):
    query_id: int | None = None
    limit: int = 12


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


class RewriteDetail(RewriteOut):
    original_sql: str
    rewritten_sql: str
    fixes: list[str]
    before_rationale: str
    after_rationale: str
    after_prunable: bool
    after_hit_partition_count: int
    after_total_partition_count: int


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
