"""ORM → schema projections (keeps services free of presentation glue)."""
import json

from src.models import AuditLog, BudgetPolicy, EstimateRun, QueryLog, RewriteSuggestion, TableMeta
from src.schemas.audit import AuditOut
from src.schemas.budget import PolicyOut
from src.schemas.estimate import EstimateRunOut
from src.schemas.query import PredicateOut, QueryDetail, QueryListItem
from src.schemas.rewrite import RewriteDetail, RewriteOut
from src.schemas.table import ColumnOut, PartitionOut, TableDetail, TableListItem


def table_item(table: TableMeta, query_count: int = 0, blocked_count: int = 0) -> TableListItem:
    return TableListItem(
        id=table.id,
        schema_name=table.schema_name,
        table_name=table.table_name,
        layer=table.layer,
        storage_format=table.storage_format,
        partition_key=table.partition_key,
        partition_count=table.partition_count,
        row_count=table.row_count,
        total_bytes=table.total_bytes,
        data_column_count=table.data_column_count,
        owner=table.owner,
        description=table.description,
        suggested_columns=list(table.suggested_columns or []),
        query_count=query_count,
        blocked_query_count=blocked_count,
    )


def table_detail(table: TableMeta, query_count: int = 0, blocked_count: int = 0) -> TableDetail:
    item = table_item(table, query_count, blocked_count)
    return TableDetail(
        **item.model_dump(),
        columns=[
            ColumnOut(
                id=c.id,
                name=c.name,
                data_type=c.data_type,
                bytes=c.bytes,
                byte_ratio=c.byte_ratio,
                ordinal=c.ordinal,
                is_partition_key=c.is_partition_key,
                note=c.note,
            )
            for c in table.columns
        ],
        partitions=[
            PartitionOut(
                id=p.id,
                dt=p.dt,
                bytes=p.bytes,
                row_count=p.row_count,
                file_count=p.file_count,
                is_current=p.is_current,
            )
            for p in table.partitions
        ],
    )


def _query_base(query: QueryLog) -> dict:
    return dict(
        id=query.id,
        external_id=query.external_id,
        title=query.title,
        source=query.source,
        submitted_by=query.submitted_by,
        query_date=query.query_date,
        duration_ms=query.duration_ms,
        is_scheduled=query.is_scheduled,
        parse_status=query.parse_status,
        target_table=query.target_table,
        prunable=query.prunable,
        blocked_reason=query.blocked_reason,
        scan_bytes=query.scan_bytes,
        scan_cost_cny=query.scan_cost_cny,
        hit_partition_count=query.hit_partition_count,
        total_partition_count=query.total_partition_count,
        col_ratio=query.col_ratio,
    )


def query_item(query: QueryLog) -> QueryListItem:
    return QueryListItem(**_query_base(query))


def query_detail(query: QueryLog, suggestion_count: int = 0) -> QueryDetail:
    predicates = []
    for row in query.predicates if isinstance(query.predicates, list) else []:
        predicates.append(PredicateOut(**row))
    return QueryDetail(
        **_query_base(query),
        sql_text=query.sql_text,
        parse_error=query.parse_error,
        blocked_expression=query.blocked_expression,
        predicates=predicates,
        hit_partitions=list(query.hit_partitions or []),
        projected_columns=list(query.projected_columns or []),
        referenced_columns=list(query.referenced_columns or []),
        has_star=query.has_star,
        full_scan_bytes=query.full_scan_bytes,
        rationale=query.rationale,
        suggestion_count=suggestion_count,
    )


def estimate_run(run: EstimateRun) -> EstimateRunOut:
    return EstimateRunOut(
        id=run.id,
        run_no=run.run_no,
        status=run.status,
        scope=run.scope,
        scope_value=run.scope_value,
        query_count=run.query_count,
        parsed_count=run.parsed_count,
        blocked_count=run.blocked_count,
        prunable_count=run.prunable_count,
        total_scan_bytes=run.total_scan_bytes,
        total_cost_cny=run.total_cost_cny,
        monthly_projected_cost_cny=run.monthly_projected_cost_cny,
        top_query_id=run.top_query_id,
        top_scan_bytes=run.top_scan_bytes,
        budget_status=run.budget_status,
        note=run.note,
        error_message=run.error_message,
        created_by=run.created_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def rewrite_base(suggestion: RewriteSuggestion) -> dict:
    query = suggestion.query
    return dict(
        id=suggestion.id,
        suggestion_no=suggestion.suggestion_no,
        query_log_id=suggestion.query_log_id,
        query_external_id=query.external_id if query else "-",
        query_title=query.title if query else "-",
        target_table=query.target_table if query else None,
        anti_patterns=list(suggestion.anti_patterns or []),
        risk_level=suggestion.risk_level,
        confidence=suggestion.confidence,
        before_scan_bytes=suggestion.before_scan_bytes,
        after_scan_bytes=suggestion.after_scan_bytes,
        saving_bytes=suggestion.saving_bytes,
        saving_cost_cny=suggestion.saving_cost_cny,
        saving_pct=suggestion.saving_pct,
        score=suggestion.score,
        status=suggestion.status,
        rationale=suggestion.rationale,
    )


def rewrite_item(suggestion: RewriteSuggestion) -> RewriteOut:
    return RewriteOut(**rewrite_base(suggestion))


def rewrite_detail(suggestion: RewriteSuggestion, extra: dict) -> RewriteDetail:
    query = suggestion.query
    original_sql = query.sql_text if query else ""
    return RewriteDetail(
        **rewrite_base(suggestion),
        original_sql=original_sql,
        rewritten_sql=suggestion.rewritten_sql,
        fixes=extra.get("fixes", []),
        before_rationale=extra.get("before_rationale", ""),
        after_rationale=extra.get("after_rationale", ""),
        after_prunable=extra.get("after_prunable", False),
        after_hit_partition_count=extra.get("after_hit_partition_count", 0),
        after_total_partition_count=extra.get("after_total_partition_count", 0),
    )


def policy(policy_row: BudgetPolicy) -> PolicyOut:
    return PolicyOut(
        id=policy_row.id,
        policy_no=policy_row.policy_no,
        name=policy_row.name,
        scope=policy_row.scope,
        scope_value=policy_row.scope_value,
        monthly_budget_cny=policy_row.monthly_budget_cny,
        unit_cost_per_gib_cny=policy_row.unit_cost_per_gib_cny,
        warn_ratio=policy_row.warn_ratio,
        critical_ratio=policy_row.critical_ratio,
        scan_alert_bytes=policy_row.scan_alert_bytes,
        is_active=policy_row.is_active,
        note=policy_row.note,
        updated_by=policy_row.updated_by,
    )


def audit(row: AuditLog) -> AuditOut:
    return AuditOut(
        id=row.id,
        actor_email=row.actor_email,
        actor_role=row.actor_role,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        method=row.method,
        path=row.path,
        status_code=row.status_code,
        created_at=row.created_at,
    )
