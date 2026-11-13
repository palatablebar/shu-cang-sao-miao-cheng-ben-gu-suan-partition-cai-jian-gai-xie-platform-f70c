"""Query log endpoints (import / ranking / detail / re-analyse)."""
from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.common import Page
from src.schemas.query import QueryDetail, QueryImportResult, QueryListItem
from src.services import query_service
from src.utils.pagination import page_params


def list_queries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort: str = Query("scan_bytes"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    status: str | None = Query(None),
    table: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[QueryListItem]:
    params = page_params(page, page_size)
    items, total = query_service.list_queries(db, params, sort, order, status, table, keyword)
    return Page[QueryListItem](items=items, total=total, page=params.page, page_size=params.page_size)


def ranking(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QueryListItem]:
    return query_service.ranking(db, limit)


def detail(
    query_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryDetail:
    return query_service.detail(db, query_id)


def analyse(
    query_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryDetail:
    request.state.audit_resource_id = query_id
    return query_service.analyze_one(db, query_id)


def import_pack(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryImportResult:
    result = query_service.import_pack(db)
    request.state.audit_detail = {"imported": result.imported, "updated": result.updated}
    return result


def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return query_service.stats(db)
