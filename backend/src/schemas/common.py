"""Shared envelopes: error payload + pagination wrapper."""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    detail: dict | None = None


def error_envelope(code: str, message: str, request_id: str | None = None, detail: dict | None = None) -> dict:
    payload = {"code": code, "message": message, "request_id": request_id}
    if detail:
        payload["detail"] = detail
    return payload


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
