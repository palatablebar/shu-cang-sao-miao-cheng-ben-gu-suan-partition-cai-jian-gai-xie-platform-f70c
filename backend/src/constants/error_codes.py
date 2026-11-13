"""Application error taxonomy (HTTP status + machine code + Chinese message)."""
from enum import Enum


class ErrorCode(str, Enum):
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    BAD_REQUEST = "bad_request"
    INTERNAL = "internal_error"


HTTP_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.INTERNAL: 500,
}


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str | None = None, detail: dict | None = None):
        self.code = code
        self.message = message or code.value
        self.detail = detail or {}
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        return HTTP_STATUS.get(self.code, 500)
