"""partfit API entrypoint.

Middleware order (outermost first):
    CORS -> RequestId -> Auth -> RateLimit -> Audit -> routes -> error handlers
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.database import init_db
from src.config.settings import settings
from src.middlewares.audit_logger import AuditMiddleware
from src.middlewares.auth import AuthMiddleware
from src.middlewares.error_handler import RequestIdMiddleware, install_error_handlers
from src.middlewares.rate_limit import RateLimitMiddleware
from src.routes import audit, auth, budget, estimates, health, queries, rewrites, tables
from src.utils.logger import log_event


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.SEED_DEMO:
        try:
            from scripts.seed_demo import run_seed

            result = run_seed()
            log_event("SEED_DEMO_FINISHED", **result)
        except Exception as exc:  # seed must never block startup
            log_event("SEED_DEMO_FAILED", error=f"{type(exc).__name__}: {exc}")
    yield


app = FastAPI(
    title="partfit API",
    description="数仓扫描成本估算与分区裁剪改写台 — 澜图零售数据平台组",
    version="1.0.0",
    lifespan=lifespan,
)

install_error_handlers(app)

# added first => innermost
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestIdMiddleware)
# added last => outermost (preflight is answered before auth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Row-Count"],
)

# The compose stack routes `/api/` through Nginx to `backend:8000/` (prefix stripped),
# while direct backend curl uses `:19243/api/...`. Mount both so the two entrypoints match.
for _prefix in ("", "/api"):
    app.include_router(health.router, prefix=_prefix)
    app.include_router(auth.router, prefix=_prefix)
    app.include_router(queries.router, prefix=_prefix)
    app.include_router(estimates.router, prefix=_prefix)
    app.include_router(rewrites.router, prefix=_prefix)
    app.include_router(tables.router, prefix=_prefix)
    app.include_router(budget.router, prefix=_prefix)
    app.include_router(audit.router, prefix=_prefix)


@app.get("/")
def index() -> dict:
    return {
        "service": "partfit-backend",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/auth/login",
            "/queries",
            "/queries/ranking",
            "/queries/import",
            "/queries/{id}",
            "/queries/{id}/analyze",
            "/estimates",
            "/rewrites",
            "/rewrites/generate",
            "/rewrites/{id}/reevaluate",
            "/rewrites/export.csv",
            "/tables",
            "/budget/overview",
            "/audit/logs",
        ],
    }
