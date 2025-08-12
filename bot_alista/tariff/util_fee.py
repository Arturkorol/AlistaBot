"""Wrapper around core utilisation fee calculation."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from tariff_engine import UTIL_CONFIG as _UTIL_CONFIG, calc_util_rub as _calc_util_rub


def calc_util_rub(
    *,
    person_type: str,
    usage: str,
    engine_cc: int,
    fuel: str,
    vehicle_kind: str,
    age_years: float,
    date_decl: date,
    avg_vehicle_cost_rub: Optional[float],
    actual_costs_rub: Optional[float],
    config: dict[str, Any] = _UTIL_CONFIG,
) -> float:
    """Public wrapper matching project naming conventions."""
    return _calc_util_rub(
        person_type=person_type,
        usage_type=usage,
        engine_cc=engine_cc,
        fuel_type=fuel,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        date_decl=date_decl,
        avg_vehicle_cost_rub=avg_vehicle_cost_rub,
        actual_costs_rub=actual_costs_rub,
        config=config,
    )


UTIL_CONFIG = _UTIL_CONFIG
