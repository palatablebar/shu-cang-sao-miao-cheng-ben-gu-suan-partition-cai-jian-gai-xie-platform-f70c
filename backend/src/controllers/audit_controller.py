"""Audit log endpoint (admin only)."""
from fastapi import Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.audit import AuditOut
from src.schemas.common import Page
from src.services import audit_service
from src.utils.pagination import page_params


def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    actor: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[AuditOut]:
    params = page_params(page, page_size)
    items, total = audit_service.list_logs(db, params, action, actor)
    return Page[AuditOut](items=items, total=total, page=params.page, page_size=params.page_size)
