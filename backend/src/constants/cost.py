"""Scan-cost arithmetic shared by services, controllers and the seed script.

Cost model (README §成本口径):
    scan_bytes  = Σ_{p ∈ P_hit} bytes_p × col_ratio
    scan_cost   = scan_bytes / GiB × COST_PER_GIB_CNY
All byte quantities are decimal-free binary units (1 GiB = 1024³ bytes).
"""
GIB = 1024 ** 3


def bytes_to_gib(value: int | float | None) -> float:
    if not value:
        return 0.0
    return float(value) / GIB


def scan_cost_cny(scan_bytes: int | float | None, cost_per_gib: float) -> float:
    """Query scan cost in CNY, rounded to 6 decimals for stable storage."""
    if not scan_bytes:
        return 0.0
    return round(bytes_to_gib(scan_bytes) * float(cost_per_gib), 6)


def monthly_projection_cny(daily_cost_cny: float, days: int, volume_scale: float) -> float:
    """单日扫描费用 → 月账单折算。

    seed 只装载 60 条代表查询（当日约 300 条），因此月折算 = 日费用 × 天数 × 放样倍数；
    倍数由 ``QUERY_VOLUME_SCALE`` 配置并在 README §成本口径 中写明。
    """
    return round(float(daily_cost_cny) * int(days) * float(volume_scale), 2)
