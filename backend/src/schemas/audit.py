"""Audit log projection."""
from datetime import datetime

from pydantic import BaseModel


class AuditOut(BaseModel):
    id: int
    actor_email: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str | None
    method: str
    path: str
    status_code: int
    created_at: datetime
