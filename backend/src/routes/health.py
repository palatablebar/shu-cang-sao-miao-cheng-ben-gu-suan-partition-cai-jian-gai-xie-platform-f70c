"""Liveness / readiness probes (public)."""
from fastapi import APIRouter
from sqlalchemy import text

from src.config.database import SessionLocal
from src.config.settings import settings
from src.utils.logger import log_event

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    database = "down"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database = "up"
    except Exception as exc:  # pragma: no cover - readiness probe
        log_event("HEALTH_DB_DOWN", error=f"{type(exc).__name__}: {exc}")
    return {
        "status": "ok" if database == "up" else "degraded",
        "service": "partfit-backend",
        "database": database,
        "catalog": settings.WAREHOUSE_CATALOG,
        "cost_per_gib_cny": settings.COST_PER_GIB_CNY,
    }
