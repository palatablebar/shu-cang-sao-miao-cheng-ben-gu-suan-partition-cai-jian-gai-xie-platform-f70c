"""TableMeta service: metadata browsing, catalog building, admin edits."""
from sqlalchemy import Integer, case, func, select
from sqlalchemy.orm import Session, selectinload

from src.analysis.sql_analyzer import catalog_from_tables
from src.constants.error_codes import AppError, ErrorCode
from src.constants.messages import MSG_TABLE_NOT_FOUND
from src.models import QueryLog, TableMeta
from src.models.base import utcnow
from src.schemas.table import TableDetail, TableListItem, TableUpdateRequest
from src.services import serializers


def _query_stats(db: Session) -> dict[str, tuple[int, int]]:
    blocked_sum = func.coalesce(func.sum(case((QueryLog.prunable.is_(False), 1), else_=0)), 0).cast(Integer)
    rows = db.execute(
        select(QueryLog.target_table, func.count(QueryLog.id).cast(Integer), blocked_sum)
        .where(QueryLog.target_table.is_not(None))
        .group_by(QueryLog.target_table)
    ).all()
    return {row[0]: (int(row[1] or 0), int(row[2] or 0)) for row in rows}


def list_tables(db: Session, layer: str | None = None) -> list[TableListItem]:
    stmt = select(TableMeta).options(selectinload(TableMeta.columns)).order_by(TableMeta.layer, TableMeta.table_name)
    if layer:
        stmt = stmt.where(TableMeta.layer == layer)
    stats = _query_stats(db)
    items = []
    for table in db.scalars(stmt):
        count, blocked = stats.get(table.table_name, (0, 0))
        items.append(serializers.table_item(table, count, blocked))
    return items


def get_table(db: Session, table_id: int) -> TableMeta:
    table = db.scalar(
        select(TableMeta)
        .options(selectinload(TableMeta.columns), selectinload(TableMeta.partitions))
        .where(TableMeta.id == table_id)
    )
    if table is None:
        raise AppError(ErrorCode.NOT_FOUND, MSG_TABLE_NOT_FOUND)
    return table


def get_table_by_name(db: Session, name: str) -> TableMeta | None:
    return db.scalar(select(TableMeta).where(TableMeta.table_name == name.lower()))


def table_detail(db: Session, table_id: int) -> TableDetail:
    table = get_table(db, table_id)
    stats = _query_stats(db)
    count, blocked = stats.get(table.table_name, (0, 0))
    return serializers.table_detail(table, count, blocked)


def update_table(db: Session, table_id: int, payload: TableUpdateRequest, actor: str) -> TableDetail:
    table = get_table(db, table_id)
    if payload.owner is not None:
        table.owner = payload.owner
    if payload.description is not None:
        table.description = payload.description
    if payload.suggested_columns is not None:
        known = {column.name for column in table.columns}
        table.suggested_columns = [name for name in payload.suggested_columns if name in known]
    table.updated_at = utcnow()
    db.commit()
    return table_detail(db, table_id)


def build_catalog(db: Session):
    tables = list(
        db.scalars(
            select(TableMeta)
            .options(selectinload(TableMeta.columns), selectinload(TableMeta.partitions))
            .order_by(TableMeta.id)
        )
    )
    return catalog_from_tables(tables)
