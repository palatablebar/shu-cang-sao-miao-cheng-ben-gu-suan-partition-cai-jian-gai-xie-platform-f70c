"""Request id + global error handlers (横切关注点 3：全局错误处理)."""
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.constants.error_codes import AppError, ErrorCode
from src.schemas.common import error_envelope
from src.utils.logger import log_event


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", None)
        log_event(
            "APP_ERROR",
            code=exc.code.value,
            message=exc.message,
            path=request.url.path,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code.value, exc.message, request_id, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                ErrorCode.VALIDATION_ERROR.value,
                "请求参数校验未通过",
                request_id,
                {"errors": exc.errors()[:6]},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        log_event("UNHANDLED_ERROR", error=f"{type(exc).__name__}: {exc}", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_envelope(ErrorCode.INTERNAL.value, "服务内部错误，请稍后重试", request_id),
        )
