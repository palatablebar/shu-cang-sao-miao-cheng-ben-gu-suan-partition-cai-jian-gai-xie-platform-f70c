"""BudgetPolicy — 月预算与告警阈值（admin 维护）。"""
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class BudgetPolicy(Base, TimestampMixin):
    __tablename__ = "budget_policy"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    scope_value: Mapped[str | None] = mapped_column(String(96), nullable=True)
    monthly_budget_cny: Mapped[float] = mapped_column(Float, nullable=False, default=18000.0)
    unit_cost_per_gib_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.30)
    warn_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    critical_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.92)
    scan_alert_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=8 * 1024 ** 3)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
