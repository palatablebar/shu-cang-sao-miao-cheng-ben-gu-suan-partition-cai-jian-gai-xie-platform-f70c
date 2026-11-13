"""RewriteSuggestion — 算法 2 产出的等价改写、风险级别与收益排序。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class RewriteSuggestion(Base, TimestampMixin):
    __tablename__ = "rewrite_suggestion"

    id: Mapped[int] = mapped_column(primary_key=True)
    suggestion_no: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    query_log_id: Mapped[int] = mapped_column(ForeignKey("query_log.id"), nullable=False, index=True)
    estimate_run_id: Mapped[int | None] = mapped_column(ForeignKey("estimate_run.id"), nullable=True)
    anti_patterns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    before_scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    after_scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    saving_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    saving_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saving_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rewritten_sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    query = relationship("QueryLog", back_populates="suggestions")
