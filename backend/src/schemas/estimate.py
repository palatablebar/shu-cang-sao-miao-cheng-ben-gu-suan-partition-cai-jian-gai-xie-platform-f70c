"""EstimateRun schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class EstimateCreateRequest(BaseModel):
    scope: str = Field(default="all", pattern="^(all|table|blocked)$")
    scope_value: str | None = None
    note: str = ""


class EstimateRunOut(BaseModel):
    id: int
    run_no: str
    status: str
    scope: str
    scope_value: str | None
    query_count: int
    parsed_count: int
    blocked_count: int
    prunable_count: int
    total_scan_bytes: int
    total_cost_cny: float
    monthly_projected_cost_cny: float
    top_query_id: int | None
    top_scan_bytes: int
    budget_status: str
    note: str
    error_message: str | None
    created_by: str
    started_at: datetime | None
    finished_at: datetime | None
