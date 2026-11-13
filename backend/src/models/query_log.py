"""QueryLog — 一条查询日志 + 算法 1 的解析/估算结果。"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class QueryLog(Base, TimestampMixin):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(48), nullable=False, default="adhoc")
    submitted_by: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    query_date: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_scheduled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- algorithm 1 output (persisted so the UI never recomputes) ---
    parse_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unparsed")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_table: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    prunable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_reason: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    blocked_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hit_partitions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hit_partition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_partition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    projected_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    referenced_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    has_star: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    scan_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    full_scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    suggestions = relationship("RewriteSuggestion", back_populates="query")
