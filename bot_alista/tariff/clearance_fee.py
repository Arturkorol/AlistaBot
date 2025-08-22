"""Common customs clearance fee ladder."""
from __future__ import annotations

import math

CLEARANCE_FEE_TABLE: list[tuple[float, float]] = [
    (200_000, 1067),
    (450_000, 2134),
    (1_200_000, 4269),
    (3_000_000, 11746),
    (5_000_000, 16524),
    (7_000_000, 20000),
    (math.inf, 30000),
]


def calc_clearance_fee_rub(customs_value_rub: float) -> float:
    """Return clearance fee (RUB) for a given customs value."""
    if customs_value_rub <= 0:
        raise ValueError("Таможенная стоимость должна быть положительной")
    for limit, fee in CLEARANCE_FEE_TABLE:
        if customs_value_rub <= limit:
            return float(fee)
    return float(CLEARANCE_FEE_TABLE[-1][1])
