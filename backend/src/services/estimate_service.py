"""EstimateRun service: create → (Celery|inline) 执行 → 聚合 → 预算判定."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.analysis.estimator import estimate_queries
from src.config.settings import settings
from src.constants.enums import BudgetStatus, RunStatus
from src.constants.error_codes import AppError, ErrorCode
from src.constants.messages import MSG_ESTIMATE_NOT_FOUND, MSG_TABLE_NOT_FOUND
from src.models import BudgetPolicy, EstimateRun, QueryLog, TableMeta
from src.schemas.estimate import EstimateCreateRequest, EstimateRunOut
from src.services import serializers, table_service
from src.utils.logger import log_event
from src.utils.pagination import PageParams

GIB = 1024 ** 3


def next_run_no(db: Session) -> str:
    prefix = datetime.now(timezone.utc).strftime("EST-%Y%m%d")
    used = db.scalar(select(func.count(EstimateRun.id)).where(EstimateRun.run_no.like(f"{prefix}-%"))) or 0
    return f"{prefix}-{int(used) + 1:02d}"


def budget_status_for(projected_cost: float, budget: float, warn: float, critical: float) -> str:
    if budget <= 0:
        return BudgetStatus.OK.value
    ratio = projected_cost / budget
    if ratio > 1:
        return BudgetStatus.OVER.value
    if ratio >= critical:
        return BudgetStatus.CRITICAL.value
    if ratio >= warn:
        return BudgetStatus.WARN.value
    return BudgetStatus.OK.value


def _global_policy(db: Session) -> BudgetPolicy | None:
    return db.scalar(
        select(BudgetPolicy)
        .where(BudgetPolicy.scope == "global", BudgetPolicy.is_active.is_(True))
        .order_by(BudgetPolicy.id)
        .limit(1)
    )


def create_run(db: Session, actor: str, payload: EstimateCreateRequest) -> EstimateRun:
    if payload.scope == "table":
        if not payload.scope_value:
            raise AppError(ErrorCode.BAD_REQUEST, "按表估算必须指定表名")
        table = db.scalar(select(TableMeta).where(TableMeta.table_name == payload.scope_value))
        if table is None:
            raise AppError(ErrorCode.NOT_FOUND, MSG_TABLE_NOT_FOUND)
    run = EstimateRun(
        run_no=next_run_no(db),
        status=RunStatus.QUEUED.value,
        scope=payload.scope,
        scope_value=payload.scope_value,
        note=payload.note,
        created_by=actor,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    dispatch(run.id)
    return run


def dispatch(run_id: int) -> str:
    """Send the run to Celery; fall back to inline execution if the broker is down."""
    if settings.ESTIMATE_INLINE:
        from src.config.database import SessionLocal

        with SessionLocal() as db:
            execute_run(db, run_id)
        return "inline"
    try:
        from src.tasks.estimate_task import run_estimate_task

        run_estimate_task.delay(run_id)
        return "celery"
    except Exception as exc:  # pragma: no cover - broker failure path
        log_event("ESTIMATE_DISPATCH_FALLBACK", run_id=run_id, error=f"{type(exc).__name__}: {exc}")
        from src.config.database import SessionLocal

        with SessionLocal() as db:
            execute_run(db, run_id)
        return "inline"


def _scope_queries(db: Session, run: EstimateRun) -> list[QueryLog]:
    stmt = select(QueryLog).order_by(QueryLog.id)
    if run.scope == "table":
        stmt = stmt.where(QueryLog.target_table == (run.scope_value or ""))
    elif run.scope == "blocked":
        stmt = stmt.where(QueryLog.prunable.is_(False), QueryLog.parse_status == "parsed")
    return list(db.scalars(stmt.limit(settings.ESTIMATE_MAX_QUERIES)))


def execute_run(db: Session, run_id: int) -> EstimateRun:
    run = db.get(EstimateRun, run_id)
    if run is None:
        raise AppError(ErrorCode.NOT_FOUND, MSG_ESTIMATE_NOT_FOUND)
    if run.status == RunStatus.COMPLETED.value:
        return run

    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(timezone.utc)
    run.error_message = None
    db.commit()

    try:
        queries = _scope_queries(db, run)
        catalog = table_service.build_catalog(db)
        summary = estimate_queries(
            [(query.id, query.sql_text) for query in queries],
            catalog,
            settings.COST_PER_GIB_CNY,
            settings.MONTHLY_QUERY_DAYS,
            settings.QUERY_VOLUME_SCALE,
        )
        by_id = {query.id: query for query in queries}
        for row in summary.rows:
            query = by_id.get(row.query_id)
            if query is None:
                continue
            from src.services.query_service import _apply_analysis

            _apply_analysis(query, row.analysis, settings.COST_PER_GIB_CNY)

        policy = _global_policy(db)
        budget = policy.monthly_budget_cny if policy else settings.DEFAULT_MONTHLY_BUDGET_CNY
        warn = policy.warn_ratio if policy else settings.DEFAULT_WARN_RATIO
        critical = policy.critical_ratio if policy else settings.DEFAULT_CRITICAL_RATIO

        run.status = RunStatus.COMPLETED.value
        run.query_count = summary.query_count
        run.parsed_count = summary.parsed_count
        run.blocked_count = summary.blocked_count
        run.prunable_count = summary.prunable_count
        run.total_scan_bytes = summary.total_scan_bytes
        run.total_cost_cny = summary.total_cost_cny
        run.monthly_projected_cost_cny = summary.monthly_projected_cost_cny
        run.top_query_id = summary.top_query_id
        run.top_scan_bytes = summary.top_scan_bytes
        run.budget_policy_id = policy.id if policy else None
        run.budget_status = budget_status_for(summary.monthly_projected_cost_cny, budget, warn, critical)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        log_event(
            "ESTIMATE_RUN_COMPLETED",
            run_no=run.run_no,
            queries=run.query_count,
            blocked=run.blocked_count,
            total_scan_bytes=run.total_scan_bytes,
        )
        return run
    except Exception as exc:
        db.rollback()
        run = db.get(EstimateRun, run_id)
        if run is not None:
            run.status = RunStatus.FAILED.value
            run.error_message = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        log_event("ESTIMATE_RUN_FAILED", run_id=run_id, error=f"{type(exc).__name__}: {exc}")
        raise


def mark_failed(db: Session, run_id: int, message: str) -> None:
    run = db.get(EstimateRun, run_id)
    if run is None or run.status == RunStatus.COMPLETED.value:
        return
    run.status = RunStatus.FAILED.value
    run.error_message = message[:900]
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def get_run(db: Session, run_id: int) -> EstimateRun:
    run = db.get(EstimateRun, run_id)
    if run is None:
        raise AppError(ErrorCode.NOT_FOUND, MSG_ESTIMATE_NOT_FOUND)
    return run


def run_detail(db: Session, run_id: int) -> EstimateRunOut:
    return serializers.estimate_run(get_run(db, run_id))


def list_runs(db: Session, params: PageParams) -> tuple[list[EstimateRunOut], int]:
    total = int(db.scalar(select(func.count(EstimateRun.id))) or 0)
    rows = db.scalars(
        select(EstimateRun).order_by(EstimateRun.id.desc()).offset(params.offset).limit(params.limit)
    )
    return [serializers.estimate_run(row) for row in rows], total
