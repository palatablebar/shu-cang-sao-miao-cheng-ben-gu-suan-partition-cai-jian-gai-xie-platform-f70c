"""Table metadata endpoints."""
from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import get_current_user
from src.models import User
from src.schemas.table import TableDetail, TableListItem, TableUpdateRequest
from src.services import table_service


def list_tables(
    layer: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TableListItem]:
    return table_service.list_tables(db, layer)


def detail(
    table_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TableDetail:
    return table_service.table_detail(db, table_id)


def update(
    table_id: int,
    payload: TableUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TableDetail:
    request.state.audit_resource_id = table_id
    return table_service.update_table(db, table_id, payload, user.display_name)
