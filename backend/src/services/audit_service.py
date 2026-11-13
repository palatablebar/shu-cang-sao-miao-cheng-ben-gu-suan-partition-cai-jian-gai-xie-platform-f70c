"""Audit log query service (written by middlewares, read by admin)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import AuditLog
from src.schemas.audit import AuditOut
from src.services import serializers
from src.utils.pagination import PageParams


def list_logs(
    db: Session, params: PageParams, action: str | None = None, actor: str | None = None
) -> tuple[list[AuditOut], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if actor:
        conditions.append(AuditLog.actor_email == actor)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset(params.offset).limit(params.limit))
    return [serializers.audit(row) for row in rows], total
