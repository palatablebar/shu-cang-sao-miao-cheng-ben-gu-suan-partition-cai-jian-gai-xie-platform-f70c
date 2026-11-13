"""Engine / session factory shared by the FastAPI app and the Celery worker."""
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=8,
    max_overflow=4,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns() -> None:
    """Additive, idempotent column upgrade for databases created before the multi-table fields.

    ``create_all`` never alters an existing table, so a DB volume seeded by an older
    image would be missing ``query_log.tables`` / ``rewrite_suggestion.table_changes``.
    Only ADD COLUMN IF NOT EXISTS statements run here — no data is rewritten.
    """
    upgrades = (
        ("query_log", "table_count", "INTEGER NOT NULL DEFAULT 0"),
        ("query_log", "tables", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
        ("query_log", "reconciliation", "JSONB NOT NULL DEFAULT '{}'::jsonb"),
        ("rewrite_suggestion", "table_changes", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
    )
    with engine.begin() as conn:
        for table, column, ddl in upgrades:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))


def init_db(max_attempts: int = 30, delay: float = 2.0) -> None:
    """Create all tables, waiting for PostgreSQL to finish its first boot."""
    import src.models  # noqa: F401

    last_error = None
    for _ in range(max_attempts):
        try:
            Base.metadata.create_all(bind=engine)
            _ensure_columns()
            return
        except Exception as exc:  # pragma: no cover - infra retry
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"database bootstrap failed: {last_error}")
