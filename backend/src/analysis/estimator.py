"""算法 1 的批量入口：逐条估算 + 批次聚合（扫描字节 / 费用 / 失效条数 / Top1）。"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.sql_analyzer import QueryAnalysis, analyze_query, catalog_from_tables

GIB = 1024 ** 3


@dataclass
class EstimateRow:
    query_id: int
    analysis: QueryAnalysis


@dataclass
class EstimateSummary:
    query_count: int = 0
    parsed_count: int = 0
    blocked_count: int = 0
    prunable_count: int = 0
    total_scan_bytes: int = 0
    total_cost_cny: float = 0.0
    monthly_projected_cost_cny: float = 0.0
    top_query_id: int | None = None
    top_scan_bytes: int = 0
    rows: list[EstimateRow] = field(default_factory=list)


def estimate_queries(
    items: list[tuple[int, str]],
    catalog,
    cost_per_gib_cny: float,
    monthly_query_days: int = 30,
    query_volume_scale: float = 1.0,
) -> EstimateSummary:
    """Estimate every (query_id, sql) pair against the metadata catalog."""
    summary = EstimateSummary()
    for query_id, sql in items:
        analysis = analyze_query(sql, catalog)
        summary.rows.append(EstimateRow(query_id=query_id, analysis=analysis))
        if analysis.parse_status != "parsed":
            continue
        summary.query_count += 1
        summary.parsed_count += 1
        if analysis.prunable:
            summary.prunable_count += 1
        else:
            summary.blocked_count += 1
        summary.total_scan_bytes += analysis.scan_bytes
        if analysis.scan_bytes > summary.top_scan_bytes:
            summary.top_scan_bytes = analysis.scan_bytes
            summary.top_query_id = query_id

    summary.total_cost_cny = round(summary.total_scan_bytes / GIB * float(cost_per_gib_cny), 6)
    summary.monthly_projected_cost_cny = round(
        summary.total_cost_cny * monthly_query_days * query_volume_scale, 2
    )
    return summary


def rows_from_tables(tables) -> dict:
    return catalog_from_tables(tables)
