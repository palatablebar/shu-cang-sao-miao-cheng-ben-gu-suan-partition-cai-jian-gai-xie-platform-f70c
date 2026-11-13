"""Number formatting shared by CSV export and API responses."""
GIB = 1024 ** 3


def gib(value: int | float | None) -> float:
    return round(float(value or 0) / GIB, 3)


def pct(value: float | None) -> str:
    return f"{float(value or 0):.2f}%"


def cny(value: float | None) -> str:
    return f"{float(value or 0):.2f}"
