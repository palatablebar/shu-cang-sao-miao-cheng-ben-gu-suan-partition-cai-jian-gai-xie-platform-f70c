"""Audit trail written by the audit middleware (横切关注点 2)."""
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String

from src.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_email: Mapped[str] = mapped_column(String(160), nullable=False, default="anonymous", index=True)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False, default="-")
    action: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="-")
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str] = mapped_column(String(8), nullable=False, default="GET")
    path: Mapped[str] = mapped_column(String(200), nullable=False, default="/")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
