"""BudgetPolicy schemas + 预算总览。"""
from pydantic import BaseModel, Field


class PolicyOut(BaseModel):
    id: int
    policy_no: str
    name: str
    scope: str
    scope_value: str | None
    monthly_budget_cny: float
    unit_cost_per_gib_cny: float
    warn_ratio: float
    critical_ratio: float
    scan_alert_bytes: int
    is_active: bool
    note: str
    updated_by: str | None


class PolicyCreateRequest(BaseModel):
    policy_no: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=2, max_length=96)
    scope: str = Field(default="global", pattern="^(global|layer|table)$")
    scope_value: str | None = None
    monthly_budget_cny: float = Field(gt=0)
    unit_cost_per_gib_cny: float = Field(default=0.30, gt=0)
    warn_ratio: float = Field(default=0.75, gt=0, le=1)
    critical_ratio: float = Field(default=0.92, gt=0, le=1)
    scan_alert_gib: float = Field(default=8.0, gt=0)
    note: str = ""


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    monthly_budget_cny: float | None = Field(default=None, gt=0)
    unit_cost_per_gib_cny: float | None = Field(default=None, gt=0)
    warn_ratio: float | None = Field(default=None, gt=0, le=1)
    critical_ratio: float | None = Field(default=None, gt=0, le=1)
    scan_alert_gib: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    note: str | None = None


class TableScanRow(BaseModel):
    table_name: str
    layer: str
    scan_bytes: int
    query_count: int
    blocked_count: int


class BudgetOverview(BaseModel):
    monthly_budget_cny: float
    projected_cost_cny: float
    month_share: float
    status: str
    unit_cost_per_gib_cny: float
    alert_bytes: int
    total_scan_bytes: int
    query_count: int
    blocked_count: int
    prunable_saving_bytes: int
    tables: list[TableScanRow]
    policies: list[PolicyOut]
