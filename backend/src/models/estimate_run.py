"""EstimateRun — 一次估算批次（后端真算，Celery 异步执行）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class EstimateRun(Base, TimestampMixin):
    __tablename__ = "estimate_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_no: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    scope: Mapped[str] = mapped_column(String(24), nullable=False, default="all")
    scope_value: Mapped[str | None] = mapped_column(String(96), nullable=True)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prunable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monthly_projected_cost_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saved_by_rewrites_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    top_query_id: Mapped[int | None] = mapped_column(ForeignKey("query_log.id"), nullable=True)
    top_scan_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    budget_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    budget_policy_id: Mapped[int | None] = mapped_column(ForeignKey("budget_policy.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
