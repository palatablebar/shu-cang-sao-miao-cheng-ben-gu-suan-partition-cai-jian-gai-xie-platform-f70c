"""Audit middleware: every mutating request that changed state leaves a row.

Only writes for non-GET methods with status < 500; the controller may attach
``request.state.audit_detail`` for structured context.
"""
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.logger import log_event

ACTION_BY_PREFIX = [
    ("/auth/login", "auth.login"),
    ("/queries/import", "query.import"),
    ("/queries/", "query.analyze"),
    ("/estimates", "estimate.run"),
    ("/rewrites/export", "rewrite.export"),
    ("/rewrites", "rewrite.generate"),
    ("/budget", "budget.update"),
    ("/tables", "table.update"),
]


def resolve_action(path: str, method: str) -> str:
    lowered = path.replace("/api", "", 1) if path.startswith("/api") else path
    for prefix, action in ACTION_BY_PREFIX:
        if lowered.startswith(prefix):
            if prefix == "/rewrites" and method == "POST" and lowered.endswith("/adopt"):
                return "rewrite.adopt"
            return action
    return f"{method.lower()}.unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return response
        try:
            from src.config.database import SessionLocal
            from src.models import AuditLog

            claims = getattr(request.state, "user_claims", None) or {}
            action = resolve_action(request.url.path, request.method)
            if response.status_code == 403:
                action = "auth.forbidden"
            with SessionLocal() as db:
                db.add(
                    AuditLog(
                        actor_email=claims.get("email", "anonymous"),
                        actor_role=claims.get("role", "-"),
                        action=action,
                        resource_type=request.url.path.split("/")[2] if request.url.path.count("/") > 2 else "-",
                        resource_id=str(getattr(request.state, "audit_resource_id", "")) or None,
                        method=request.method,
                        path=request.url.path[:200],
                        status_code=response.status_code,
                        ip=(request.client.host if request.client else None),
                        detail=getattr(request.state, "audit_detail", {}) or {},
                    )
                )
                db.commit()
        except Exception as exc:  # auditing must never break the request
            log_event("AUDIT_WRITE_FAILED", error=f"{type(exc).__name__}: {exc}")
        return response
