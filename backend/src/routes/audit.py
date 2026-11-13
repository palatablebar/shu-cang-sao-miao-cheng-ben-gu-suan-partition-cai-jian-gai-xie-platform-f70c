"""Audit router (admin only)."""
from fastapi import APIRouter, Depends

from src.controllers import audit_controller
from src.middlewares.rbac import require_roles
from src.schemas.audit import AuditOut
from src.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["audit"])

router.add_api_route(
    "/logs",
    audit_controller.list_logs,
    methods=["GET"],
    response_model=Page[AuditOut],
    dependencies=[Depends(require_roles("admin"))],
)
