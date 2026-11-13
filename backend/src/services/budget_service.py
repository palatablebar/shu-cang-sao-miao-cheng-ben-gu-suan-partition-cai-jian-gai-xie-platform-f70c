"""BudgetPolicy service + 预算总览（月账单 vs 预算阈值）。"""
from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import BudgetStatus
from src.constants.error_codes import AppError, ErrorCode
from src.constants.cost import monthly_projection_cny
from src.constants.messages import MSG_POLICY_NOT_FOUND
from src.models import BudgetPolicy, EstimateRun, QueryLog, RewriteSuggestion, TableMeta
from src.schemas.budget import (
    BudgetOverview,
    PolicyCreateRequest,
    PolicyOut,
    PolicyUpdateRequest,
    TableScanRow,
)
from src.services import serializers

GIB = 1024 ** 3


def list_policies(db: Session, active_only: bool = False) -> list[PolicyOut]:
    stmt = select(BudgetPolicy).order_by(BudgetPolicy.scope, BudgetPolicy.policy_no)
    if active_only:
        stmt = stmt.where(BudgetPolicy.is_active.is_(True))
    return [serializers.policy(row) for row in db.scalars(stmt)]


def get_policy(db: Session, policy_id: int) -> BudgetPolicy:
    policy = db.get(BudgetPolicy, policy_id)
    if policy is None:
        raise AppError(ErrorCode.NOT_FOUND, MSG_POLICY_NOT_FOUND)
    return policy


def _apply_payload(policy: BudgetPolicy, payload: PolicyUpdateRequest) -> None:
    if payload.name is not None:
        policy.name = payload.name
    if payload.monthly_budget_cny is not None:
        policy.monthly_budget_cny = payload.monthly_budget_cny
    if payload.unit_cost_per_gib_cny is not None:
        policy.unit_cost_per_gib_cny = payload.unit_cost_per_gib_cny
    if payload.warn_ratio is not None:
        policy.warn_ratio = payload.warn_ratio
    if payload.critical_ratio is not None:
        policy.critical_ratio = payload.critical_ratio
    if payload.scan_alert_gib is not None:
        policy.scan_alert_bytes = int(payload.scan_alert_gib * GIB)
    if payload.is_active is not None:
        policy.is_active = payload.is_active
    if payload.note is not None:
        policy.note = payload.note


def update_policy(db: Session, policy_id: int, payload: PolicyUpdateRequest, actor: str) -> PolicyOut:
    policy = get_policy(db, policy_id)
    _apply_payload(policy, payload)
    policy.updated_by = actor
    db.commit()
    db.refresh(policy)
    return serializers.policy(policy)


def create_policy(db: Session, payload: PolicyCreateRequest, actor: str) -> PolicyOut:
    existing = db.scalar(select(BudgetPolicy).where(BudgetPolicy.policy_no == payload.policy_no))
    if existing is not None:
        raise AppError(ErrorCode.CONFLICT, f"策略编号 {payload.policy_no} 已存在")
    policy = BudgetPolicy(
        policy_no=payload.policy_no,
        name=payload.name,
        scope=payload.scope,
        scope_value=payload.scope_value,
        monthly_budget_cny=payload.monthly_budget_cny,
        unit_cost_per_gib_cny=payload.unit_cost_per_gib_cny,
        warn_ratio=payload.warn_ratio,
        critical_ratio=payload.critical_ratio,
        scan_alert_bytes=int(payload.scan_alert_gib * GIB),
        note=payload.note,
        updated_by=actor,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return serializers.policy(policy)


def _status(projected: float, budget: float, warn: float, critical: float) -> str:
    if budget <= 0:
        return BudgetStatus.OK.value
    ratio = projected / budget
    if ratio > 1:
        return BudgetStatus.OVER.value
    if ratio >= critical:
        return BudgetStatus.CRITICAL.value
    if ratio >= warn:
        return BudgetStatus.WARN.value
    return BudgetStatus.OK.value


def overview(db: Session) -> BudgetOverview:
    policy = db.scalar(
        select(BudgetPolicy)
        .where(BudgetPolicy.scope == "global", BudgetPolicy.is_active.is_(True))
        .order_by(BudgetPolicy.id)
        .limit(1)
    )
    budget = policy.monthly_budget_cny if policy else settings.DEFAULT_MONTHLY_BUDGET_CNY
    warn = policy.warn_ratio if policy else settings.DEFAULT_WARN_RATIO
    critical = policy.critical_ratio if policy else settings.DEFAULT_CRITICAL_RATIO
    unit_cost = policy.unit_cost_per_gib_cny if policy else settings.COST_PER_GIB_CNY
    alert_bytes = policy.scan_alert_bytes if policy else int(8 * GIB)

    # 预算总览只看全量批次：按表/按失效范围的专项批次会把总扫描量算小。
    latest_run = db.scalar(
        select(EstimateRun)
        .where(EstimateRun.status == "completed", EstimateRun.scope == "all")
        .order_by(EstimateRun.id.desc())
        .limit(1)
    )
    if latest_run is not None:
        total_scan = int(latest_run.total_scan_bytes)
        query_count = int(latest_run.query_count)
        blocked = int(latest_run.blocked_count)
        projected = float(latest_run.monthly_projected_cost_cny)
    else:
        total_scan = int(db.scalar(select(func.coalesce(func.sum(QueryLog.scan_bytes), 0))) or 0)
        query_count = int(db.scalar(select(func.count(QueryLog.id))) or 0)
        blocked = int(
            db.scalar(
                select(func.count(QueryLog.id)).where(QueryLog.prunable.is_(False), QueryLog.parse_status == "parsed")
            )
            or 0
        )
        projected = monthly_projection_cny(
            total_scan / GIB * unit_cost, settings.MONTHLY_QUERY_DAYS, settings.QUERY_VOLUME_SCALE
        )

    rows = db.execute(
        select(
            QueryLog.target_table,
            func.coalesce(func.sum(QueryLog.scan_bytes), 0),
            func.count(QueryLog.id),
            func.coalesce(
                func.sum(case((QueryLog.prunable.is_(False), 1), else_=0)), 0
            ).cast(Integer),
        )
        .where(QueryLog.target_table.is_not(None))
        .group_by(QueryLog.target_table)
        .order_by(func.coalesce(func.sum(QueryLog.scan_bytes), 0).desc())
    ).all()
    layers = {table.table_name: table.layer for table in db.scalars(select(TableMeta))}
    tables = [
        TableScanRow(
            table_name=row[0],
            layer=layers.get(row[0], "DWD"),
            scan_bytes=int(row[1] or 0),
            query_count=int(row[2] or 0),
            blocked_count=int(row[3] or 0),
        )
        for row in rows
    ]
    saving = int(
        db.scalar(
            select(func.coalesce(func.sum(RewriteSuggestion.saving_bytes), 0)).where(
                RewriteSuggestion.status.in_(["pending", "adopted"])
            )
        )
        or 0
    )
    return BudgetOverview(
        monthly_budget_cny=budget,
        projected_cost_cny=round(projected, 2),
        month_share=round(projected / budget, 4) if budget else 0.0,
        status=_status(projected, budget, warn, critical),
        unit_cost_per_gib_cny=unit_cost,
        alert_bytes=alert_bytes,
        total_scan_bytes=total_scan,
        query_count=query_count,
        blocked_count=blocked,
        prunable_saving_bytes=saving,
        tables=tables,
        policies=list_policies(db),
    )
