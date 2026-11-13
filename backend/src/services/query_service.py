"""QueryLog service: import pack, (re)analyse, cost ranking, detail."""
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from src.analysis.sql_analyzer import QueryAnalysis, analyze_query
from src.config.settings import settings
from src.constants.error_codes import AppError, ErrorCode
from src.constants.messages import MSG_QUERY_NOT_FOUND
from src.models import QueryLog
from src.schemas.query import QueryDetail, QueryImportResult, QueryListItem
from src.services import serializers, table_service
from src.utils.pagination import PageParams

SORT_FIELDS = {
    "scan_bytes": QueryLog.scan_bytes,
    "scan_cost": QueryLog.scan_cost_cny,
    "duration": QueryLog.duration_ms,
    "query_date": QueryLog.query_date,
    "external_id": QueryLog.external_id,
}


def get_query(db: Session, query_id: int) -> QueryLog:
    query = db.get(QueryLog, query_id)
    if query is None:
        raise AppError(ErrorCode.NOT_FOUND, MSG_QUERY_NOT_FOUND)
    return query


def detail(db: Session, query_id: int) -> QueryDetail:
    query = get_query(db, query_id)
    suggestion_count = len(query.suggestions) if query.suggestions is not None else 0
    return serializers.query_detail(query, suggestion_count)


def _apply_analysis(query: QueryLog, analysis: QueryAnalysis, cost_per_gib: float) -> None:
    query.parse_status = analysis.parse_status
    query.parse_error = analysis.parse_error
    query.target_table = analysis.target_table
    query.prunable = analysis.prunable
    query.blocked_reason = analysis.blocked_reason
    query.blocked_expression = analysis.blocked_expression
    query.predicates = analysis.predicates
    query.hit_partitions = analysis.hit_partitions
    query.hit_partition_count = analysis.hit_partition_count
    query.total_partition_count = analysis.total_partition_count
    query.col_ratio = analysis.col_ratio
    query.projected_columns = analysis.projected_columns
    query.referenced_columns = analysis.referenced_columns
    query.has_star = analysis.has_star
    query.scan_bytes = analysis.scan_bytes
    query.scan_cost_cny = round(analysis.scan_bytes / (1024 ** 3) * cost_per_gib, 6)
    query.full_scan_bytes = analysis.full_scan_bytes
    query.rationale = analysis.rationale
    query.analyzed_at = datetime.now(timezone.utc)


def analyze_and_store(db: Session, query: QueryLog, catalog=None) -> QueryAnalysis:
    catalog = catalog if catalog is not None else table_service.build_catalog(db)
    analysis = analyze_query(query.sql_text, catalog)
    _apply_analysis(query, analysis, settings.COST_PER_GIB_CNY)
    return analysis


def analyze_one(db: Session, query_id: int) -> QueryDetail:
    query = get_query(db, query_id)
    analyze_and_store(db, query)
    db.commit()
    return detail(db, query_id)


def import_pack(db: Session) -> QueryImportResult:
    """Idempotent import of the bundled 60-row query log (natural key = external_id)."""
    from scripts.demo_dataset import build_queries

    catalog = table_service.build_catalog(db)
    imported = updated = 0
    for row in build_queries():
        existing = db.scalar(select(QueryLog).where(QueryLog.external_id == row["external_id"]))
        if existing is None:
            existing = QueryLog(external_id=row["external_id"])
            db.add(existing)
            imported += 1
        else:
            updated += 1
        existing.title = row["title"]
        existing.sql_text = row["sql_text"]
        existing.source = row["source"]
        existing.submitted_by = row["submitted_by"]
        existing.query_date = row["query_date"]
        existing.duration_ms = row["duration_ms"]
        existing.is_scheduled = row["is_scheduled"]
        analyze_and_store(db, existing, catalog)
    db.commit()

    total = db.scalar(select(func.count(QueryLog.id))) or 0
    blocked = db.scalar(
        select(func.count(QueryLog.id)).where(QueryLog.prunable.is_(False), QueryLog.parse_status == "parsed")
    ) or 0
    return QueryImportResult(
        imported=imported,
        updated=updated,
        total=int(total),
        analysed=int(total),
        blocked=int(blocked),
        message=f"导入完成：新增 {imported} 条、更新 {updated} 条，裁剪失效 {int(blocked)} 条",
    )


def list_queries(
    db: Session,
    params: PageParams,
    sort: str = "scan_bytes",
    order: str = "desc",
    status: str | None = None,
    table: str | None = None,
    keyword: str | None = None,
) -> tuple[list[QueryListItem], int]:
    stmt = select(QueryLog)
    count_stmt = select(func.count(QueryLog.id))
    conditions = []
    if status == "blocked":
        conditions.append(QueryLog.prunable.is_(False))
        conditions.append(QueryLog.parse_status == "parsed")
    elif status == "prunable":
        conditions.append(QueryLog.prunable.is_(True))
    elif status in ("unparsed", "missing_table"):
        conditions.append(QueryLog.parse_status == status)
    if table:
        conditions.append(QueryLog.target_table == table)
    if keyword:
        conditions.append(QueryLog.title.ilike(f"%{keyword}%"))
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    column = SORT_FIELDS.get(sort, QueryLog.scan_bytes)
    stmt = stmt.order_by(column.asc() if order == "asc" else column.desc(), QueryLog.id.asc())
    total = int(db.scalar(count_stmt) or 0)
    items = [serializers.query_item(row) for row in db.scalars(stmt.offset(params.offset).limit(params.limit))]
    return items, total


def ranking(db: Session, limit: int = 12) -> list[QueryListItem]:
    stmt = select(QueryLog).order_by(QueryLog.scan_bytes.desc(), QueryLog.id.asc()).limit(limit)
    return [serializers.query_item(row) for row in db.scalars(stmt)]


def stats(db: Session) -> dict:
    total = int(db.scalar(select(func.count(QueryLog.id))) or 0)
    blocked = int(
        db.scalar(
            select(func.count(QueryLog.id)).where(QueryLog.prunable.is_(False), QueryLog.parse_status == "parsed")
        )
        or 0
    )
    prunable = int(db.scalar(select(func.count(QueryLog.id)).where(QueryLog.prunable.is_(True))) or 0)
    total_scan = int(db.scalar(select(func.coalesce(func.sum(QueryLog.scan_bytes), 0))) or 0)
    top = db.scalar(select(QueryLog).order_by(QueryLog.scan_bytes.desc()).limit(1))
    return {
        "query_count": total,
        "blocked_count": blocked,
        "prunable_count": prunable,
        "total_scan_bytes": total_scan,
        "top_scan_bytes": int(top.scan_bytes) if top else 0,
        "top_query_id": top.id if top else None,
    }
