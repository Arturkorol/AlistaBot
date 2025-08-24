"""Shared customs clearance fee ladder and helpers."""

from __future__ import annotations

from typing import Sequence, Tuple

CLEARANCE_FEE_RANGES: Tuple[Tuple[float, float], ...] = (
    (200_000, 1_067.0),
    (450_000, 2_134.0),
    (1_200_000, 4_269.0),
    (3_000_000, 11_746.0),
    (5_000_000, 16_524.0),
    (7_000_000, 20_000.0),
    (float("inf"), 30_000.0),
)


def calc_clearance_fee_rub(
    customs_value_rub: float,
    ranges: Sequence[Tuple[float, float]] = CLEARANCE_FEE_RANGES,
) -> float:
    """Return clearance fee based on customs value."""
    v = float(customs_value_rub)
    if v <= 0:
        raise ValueError("Customs value must be positive")
    for limit, fee in ranges:
        if v <= limit:
            return float(fee)
    return float(ranges[-1][1])


__all__ = ["CLEARANCE_FEE_RANGES", "calc_clearance_fee_rub"]

