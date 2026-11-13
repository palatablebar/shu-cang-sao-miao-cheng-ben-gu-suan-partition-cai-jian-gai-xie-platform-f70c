"""QueryLog schemas — 解析结果字段与算法 1 输出一一对应。"""
from pydantic import BaseModel


class PredicateOut(BaseModel):
    expression: str
    operator: str
    literal: str
    usable: bool
    reason: str
    wrapper_kind: str | None = None


class QueryListItem(BaseModel):
    id: int
    external_id: str
    title: str
    source: str
    submitted_by: str
    query_date: str
    duration_ms: int
    is_scheduled: bool
    parse_status: str
    target_table: str | None
    prunable: bool
    blocked_reason: str
    scan_bytes: int
    scan_cost_cny: float
    hit_partition_count: int
    total_partition_count: int
    col_ratio: float


class QueryDetail(QueryListItem):
    sql_text: str
    parse_error: str | None
    blocked_expression: str | None
    predicates: list[PredicateOut]
    hit_partitions: list[str]
    projected_columns: list[str]
    referenced_columns: list[str]
    has_star: bool
    full_scan_bytes: int
    rationale: str
    suggestion_count: int = 0


class QueryImportResult(BaseModel):
    imported: int
    updated: int
    total: int
    analysed: int
    blocked: int
    message: str
