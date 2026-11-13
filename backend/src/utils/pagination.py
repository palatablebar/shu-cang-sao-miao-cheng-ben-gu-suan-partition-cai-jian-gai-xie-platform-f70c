"""Offset pagination helpers."""
from dataclasses import dataclass

from src.config.settings import settings


@dataclass
class PageParams:
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (max(1, self.page) - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def page_params(page: int = 1, page_size: int = 20) -> PageParams:
    size = max(1, min(page_size, settings.QUERY_PAGE_MAX))
    return PageParams(page=max(1, page), page_size=size)
