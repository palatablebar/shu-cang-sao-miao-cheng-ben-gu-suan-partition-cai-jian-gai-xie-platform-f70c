"""Idempotent demo seed for the partfit demo tenant（澜图零售 · 数据平台组）.

Runnable both ways:
    python -m scripts.seed_demo            # from /app inside the backend container
    python scripts/seed_demo.py

Natural keys (重复执行不新增、不覆盖用户修改):
    users.email · table_meta.table_name · table_column(table_id,name)
    partition_meta(table_id,dt) · query_log.external_id · estimate_run.run_no
    rewrite_suggestion.suggestion_no · budget_policy.policy_no

The last stdout line is always the stable contract line:
    SEED_SUMMARY brand=partfit tables=6 partitions=90 queries=60 estimates=2 suggestions=12 users=3
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

if __package__ in (None, ""):  # allow `python scripts/seed_demo.py`
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from scripts import demo_dataset  # noqa: E402
from src.analysis.estimator import estimate_queries  # noqa: E402
from src.analysis.sql_analyzer import analyze_query  # noqa: E402
from src.config.database import SessionLocal, init_db  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.constants.enums import RunStatus  # noqa: E402
from src.models import (  # noqa: E402
    BudgetPolicy,
    EstimateRun,
    PartitionMeta,
    QueryLog,
    RewriteSuggestion,
    TableColumn,
    TableMeta,
    User,
)
from src.models.base import utcnow  # noqa: E402
from src.services import query_service, rewrite_service, table_service  # noqa: E402
from src.services.estimate_service import budget_status_for  # noqa: E402
from src.utils.password import hash_password  # noqa: E402

GIB = 1024 ** 3


def _log(message: str) -> None:
    print(f"[seed] {message}", flush=True)


def seed_users(db) -> int:
    created = 0
    for row in demo_dataset.USERS:
        existing = db.scalar(select(User).where(User.email == row["email"]))
        if existing is not None:
            continue
        db.add(
            User(
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                team=row["team"],
                password_hash=hash_password(demo_dataset.PASSWORD),
            )
        )
        created += 1
    if created:
        db.commit()
    _log(f"users created={created} total={len(demo_dataset.USERS)}")
    return created


def seed_tables(db) -> int:
    created = 0
    for spec in demo_dataset.build_tables():
        table = db.scalar(select(TableMeta).where(TableMeta.table_name == spec["table_name"]))
        if table is None:
            table = TableMeta(table_name=spec["table_name"])
            db.add(table)
            created += 1
        table.schema_name = spec["schema_name"]
        table.layer = spec["layer"]
        table.storage_format = spec["storage_format"]
        table.partition_key = spec["partition_key"]
        table.partition_type = spec["partition_type"]
        table.partition_count = spec["partition_count"]
        table.row_count = spec["row_count"]
        table.total_bytes = spec["total_bytes"]
        table.data_column_count = spec["data_column_count"]
        table.owner = spec["owner"]
        table.description = spec["description"]
        table.suggested_columns = spec["suggested_columns"]
        table.last_analyzed_dt = spec["last_analyzed_dt"]
        db.flush()

        for column_spec in spec["columns"]:
            column = db.scalar(
                select(TableColumn).where(
                    TableColumn.table_id == table.id, TableColumn.name == column_spec["name"]
                )
            )
            if column is None:
                column = TableColumn(table_id=table.id, name=column_spec["name"])
                db.add(column)
            column.data_type = column_spec["data_type"]
            column.bytes = column_spec["bytes"]
            column.byte_ratio = column_spec["byte_ratio"]
            column.ordinal = column_spec["ordinal"]
            column.is_partition_key = column_spec["is_partition_key"]
            column.note = column_spec["note"]

        for partition_spec in spec["partitions"]:
            partition = db.scalar(
                select(PartitionMeta).where(
                    PartitionMeta.table_id == table.id, PartitionMeta.dt == partition_spec["dt"]
                )
            )
            if partition is None:
                partition = PartitionMeta(table_id=table.id, dt=partition_spec["dt"])
                db.add(partition)
            partition.bytes = partition_spec["bytes"]
            partition.row_count = partition_spec["row_count"]
            partition.file_count = partition_spec["file_count"]
            partition.is_current = partition_spec["is_current"]
        db.flush()
    db.commit()
    _log(f"tables created={created} total={len(demo_dataset.TABLES)}")
    return created


def seed_queries(db) -> int:
    created = 0
    catalog = table_service.build_catalog(db)
    for row in demo_dataset.build_queries():
        query = db.scalar(select(QueryLog).where(QueryLog.external_id == row["external_id"]))
        if query is None:
            query = QueryLog(external_id=row["external_id"])
            db.add(query)
            created += 1
        query.title = row["title"]
        query.sql_text = row["sql_text"]
        query.source = row["source"]
        query.submitted_by = row["submitted_by"]
        query.query_date = row["query_date"]
        query.duration_ms = row["duration_ms"]
        query.is_scheduled = row["is_scheduled"]
        query_service._apply_analysis(query, analyze_query(query.sql_text, catalog), settings.COST_PER_GIB_CNY)
    db.commit()
    _log(f"queries created={created} total={len(demo_dataset.build_queries())}")
    return created


def seed_estimates(db) -> int:
    catalog = table_service.build_catalog(db)
    queries = list(db.scalars(select(QueryLog).order_by(QueryLog.id)))
    by_id = {query.id: query for query in queries}
    policy = db.scalar(
        select(BudgetPolicy)
        .where(BudgetPolicy.scope == "global", BudgetPolicy.is_active.is_(True))
        .order_by(BudgetPolicy.id)
        .limit(1)
    )
    budget = policy.monthly_budget_cny if policy else settings.DEFAULT_MONTHLY_BUDGET_CNY
    warn = policy.warn_ratio if policy else settings.DEFAULT_WARN_RATIO
    critical = policy.critical_ratio if policy else settings.DEFAULT_CRITICAL_RATIO

    created = 0
    for spec in demo_dataset.SEED_ESTIMATES:
        existing = db.scalar(select(EstimateRun).where(EstimateRun.run_no == spec["run_no"]))
        if existing is not None:
            continue
        selected = queries
        if spec["scope"] == "table":
            selected = [q for q in queries if q.target_table == spec["scope_value"]]
        summary = estimate_queries(
            [(q.id, q.sql_text) for q in selected],
            catalog,
            settings.COST_PER_GIB_CNY,
            settings.MONTHLY_QUERY_DAYS,
            settings.QUERY_VOLUME_SCALE,
        )
        for row in summary.rows:
            query = by_id.get(row.query_id)
            if query is not None:
                query_service._apply_analysis(query, row.analysis, settings.COST_PER_GIB_CNY)
        db.add(
            EstimateRun(
                run_no=spec["run_no"],
                status=RunStatus.COMPLETED.value,
                scope=spec["scope"],
                scope_value=spec["scope_value"],
                query_count=summary.query_count,
                parsed_count=summary.parsed_count,
                blocked_count=summary.blocked_count,
                prunable_count=summary.prunable_count,
                total_scan_bytes=summary.total_scan_bytes,
                total_cost_cny=summary.total_cost_cny,
                monthly_projected_cost_cny=summary.monthly_projected_cost_cny,
                top_query_id=summary.top_query_id,
                top_scan_bytes=summary.top_scan_bytes,
                budget_status=budget_status_for(summary.monthly_projected_cost_cny, budget, warn, critical),
                budget_policy_id=policy.id if policy else None,
                note=spec["note"],
                created_by=spec["created_by"],
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        )
        created += 1
        db.commit()
    _log(f"estimates created={created} total={len(demo_dataset.SEED_ESTIMATES)}")
    return created


def seed_budget(db) -> int:
    created = 0
    for spec in demo_dataset.BUDGET_POLICIES:
        existing = db.scalar(select(BudgetPolicy).where(BudgetPolicy.policy_no == spec["policy_no"]))
        if existing is not None:
            continue
        db.add(
            BudgetPolicy(
                policy_no=spec["policy_no"],
                name=spec["name"],
                scope=spec["scope"],
                scope_value=spec["scope_value"],
                monthly_budget_cny=spec["monthly_budget_cny"],
                unit_cost_per_gib_cny=spec["unit_cost_per_gib_cny"],
                warn_ratio=spec["warn_ratio"],
                critical_ratio=spec["critical_ratio"],
                scan_alert_bytes=int(spec["scan_alert_gib"] * GIB),
                is_active=spec["is_active"],
                note=spec["note"],
                updated_by=demo_dataset.ADMIN,
            )
        )
        created += 1
    if created:
        db.commit()
    _log(f"budget policies created={created} total={len(demo_dataset.BUDGET_POLICIES)}")
    return created


def expected_suggestion_nos(db) -> list[str]:
    """Top-12 ranking is deterministic; recompute the natural keys for the summary."""
    catalog = table_service.build_catalog(db)
    from src.analysis.rewriter import build_rewrite

    scored = []
    for query in db.scalars(
        select(QueryLog).where(QueryLog.prunable.is_(False), QueryLog.parse_status == "parsed")
    ):
        result = build_rewrite(
            query.sql_text,
            catalog,
            window_days=settings.REWRITE_WINDOW_DAYS,
            cost_per_gib_cny=settings.COST_PER_GIB_CNY,
        )
        if result.rewritable:
            scored.append((query, result))
    scored.sort(key=lambda item: (-item[1].score, item[0].external_id))
    return [rewrite_service.suggestion_no_for(query) for query, _ in scored[:12]]


def seed_suggestions(db) -> int:
    created = rewrite_service.rebuild_suggestions(db, limit=12)
    _log(f"suggestions created={created} expected=12")
    return created


def collect_counts(db) -> dict:
    table_names = [spec["table_name"] for spec in demo_dataset.TABLES]
    emails = [row["email"] for row in demo_dataset.USERS]
    run_nos = [spec["run_no"] for spec in demo_dataset.SEED_ESTIMATES]
    expected_nos = expected_suggestion_nos(db)

    tables = int(
        db.scalar(select(func.count(TableMeta.id)).where(TableMeta.table_name.in_(table_names))) or 0
    )
    partitions = int(
        db.scalar(
            select(func.count(PartitionMeta.id))
            .join(TableMeta, PartitionMeta.table_id == TableMeta.id)
            .where(TableMeta.table_name.in_(table_names))
        )
        or 0
    )
    queries = int(
        db.scalar(
            select(func.count(QueryLog.id)).where(
                QueryLog.external_id.in_([f"QL-{i:04d}" for i in range(1, len(demo_dataset.build_queries()) + 1)])
            )
        )
        or 0
    )
    estimates = int(db.scalar(select(func.count(EstimateRun.id)).where(EstimateRun.run_no.in_(run_nos))) or 0)
    suggestions = int(
        db.scalar(
            select(func.count(RewriteSuggestion.id)).where(RewriteSuggestion.suggestion_no.in_(expected_nos))
        )
        or 0
    )
    users = int(db.scalar(select(func.count(User.id)).where(User.email.in_(emails))) or 0)
    return {
        "tables": tables,
        "partitions": partitions,
        "queries": queries,
        "estimates": estimates,
        "suggestions": suggestions,
        "users": users,
    }


def run_seed() -> dict:
    """Run the whole idempotent seed inside one session; returns the summary dict."""
    init_db()
    with SessionLocal() as db:
        seed_users(db)
        seed_budget(db)
        seed_tables(db)
        seed_queries(db)
        seed_estimates(db)
        seed_suggestions(db)
        counts = collect_counts(db)
    summary = {
        "SEED_SUMMARY": (
            f"SEED_SUMMARY brand={demo_dataset.BRAND} tables={counts['tables']} "
            f"partitions={counts['partitions']} queries={counts['queries']} "
            f"estimates={counts['estimates']} suggestions={counts['suggestions']} "
            f"users={counts['users']}"
        ),
        **counts,
    }
    print(summary["SEED_SUMMARY"], flush=True)
    return summary


if __name__ == "__main__":
    run_seed()
