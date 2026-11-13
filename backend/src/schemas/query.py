"""QueryLog schemas — 解析结果字段与算法 1 输出一一对应。"""
from pydantic import BaseModel


class PredicateOut(BaseModel):
    expression: str
    operator: str
    literal: str
    usable: bool
    reason: str
    wrapper_kind: str | None = None
    table: str | None = None
    table_alias: str | None = None


class TableAnalysisOut(BaseModel):
    """算法 1 的单表拆解：扫描字节 / 命中分区 / 裁剪原因，可与查询总量对账。"""

    table_name: str
    qualified_name: str = ""
    alias: str = ""
    status: str = "analyzed"
    partition_key: str | None = None
    prunable: bool = False
    blocked_reason: str = "none"
    blocked_expression: str | None = None
    predicates: list[PredicateOut] = []
    hit_partitions: list[str] = []
    hit_partition_count: int = 0
    total_partition_count: int = 0
    hit_bytes: int = 0
    col_ratio: float = 1.0
    projected_columns: list[str] = []
    referenced_columns: list[str] = []
    has_star: bool = False
    scan_bytes: int = 0
    full_scan_bytes: int = 0
    counted_in_total: bool = True
    rationale: str = ""


class ReconciliationOut(BaseModel):
    query_scan_bytes: int
    table_scan_sum_bytes: int
    delta_bytes: int
    balanced: bool
    missing_table_count: int = 0


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
    table_count: int = 0
    tables: list[TableAnalysisOut] = []
    reconciliation: ReconciliationOut | None = None


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
    table_scan_sum_bytes: int = 0


class QueryImportResult(BaseModel):
    imported: int
    updated: int
    total: int
    analysed: int
    blocked: int
    message: str
