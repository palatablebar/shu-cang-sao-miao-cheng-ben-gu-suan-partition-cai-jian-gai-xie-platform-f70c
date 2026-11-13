"""Fixed-window in-process rate limit per actor (横切关注点 3：限流/配额).

Single-container backend keeps this in memory; the window is generous (240 rpm by
default) so demo flows never trip it while a runaway loop does.
"""
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config.settings import settings
from src.constants.error_codes import ErrorCode
from src.constants.messages import MSG_QUOTA_EXCEEDED
from src.schemas.common import error_envelope

BUCKETS: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.rstrip("/") in ("/health", "/api/health"):
            return await call_next(request)
        claims = getattr(request.state, "user_claims", None) or {}
        key = claims.get("email") or (request.client.host if request.client else "anonymous")
        now = time.time()
        window_start = now - settings.RATE_WINDOW_SECONDS
        hits = [ts for ts in BUCKETS[key] if ts >= window_start]
        if len(hits) >= settings.RATE_WINDOW_MAX:
            BUCKETS[key] = hits
            return JSONResponse(
                status_code=429,
                content=error_envelope(
                    ErrorCode.RATE_LIMITED.value,
                    MSG_QUOTA_EXCEEDED,
                    getattr(request.state, "request_id", None),
                    {"window_seconds": settings.RATE_WINDOW_SECONDS, "max": settings.RATE_WINDOW_MAX},
                ),
            )
        hits.append(now)
        BUCKETS[key] = hits
        return await call_next(request)
