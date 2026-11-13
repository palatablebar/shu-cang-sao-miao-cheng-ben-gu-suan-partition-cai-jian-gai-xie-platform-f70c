"""Rewrite suggestion endpoints + CSV export."""
from fastapi import Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.common import Page
from src.schemas.rewrite import (
    RewriteDetail,
    RewriteGenerateRequest,
    RewriteOut,
    RewriteReevaluateOut,
)
from src.services import rewrite_service
from src.utils.pagination import page_params


def list_suggestions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    sort: str = Query("score"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[RewriteOut]:
    params = page_params(page, page_size)
    items, total = rewrite_service.list_suggestions(db, params, status, sort)
    return Page[RewriteOut](items=items, total=total, page=params.page, page_size=params.page_size)


def detail(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RewriteDetail:
    return rewrite_service.detail(db, suggestion_id)


def generate(
    payload: RewriteGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RewriteDetail:
    if payload.query_id is None:
        from src.constants.error_codes import AppError, ErrorCode

        raise AppError(ErrorCode.BAD_REQUEST, "请指定 query_id（单条生成改写）")
    detail_row = rewrite_service.generate_for_query(db, payload.query_id, user.display_name)
    request.state.audit_resource_id = detail_row.suggestion_no
    request.state.audit_detail = {"saving_pct": detail_row.saving_pct}
    return detail_row


def reevaluate(
    suggestion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RewriteReevaluateOut:
    result = rewrite_service.reevaluate(db, suggestion_id)
    request.state.audit_resource_id = result.suggestion_no
    request.state.audit_detail = {"saving_pct": result.saving_pct}
    return result


def adopt(
    suggestion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RewriteOut:
    request.state.audit_resource_id = suggestion_id
    return rewrite_service.adopt(db, suggestion_id, user.display_name)


def export_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    content, rows = rewrite_service.export_csv(db)
    request.state.audit_resource_id = "optimisation-list"
    request.state.audit_detail = {"rows": rows}
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="partfit-optimisation-list.csv"',
            "X-Row-Count": str(rows),
        },
    )
