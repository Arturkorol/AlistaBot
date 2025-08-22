from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

try:  # pragma: no cover - external package is optional
    from tks_api_official import CustomsCalculator
except Exception:  # pragma: no cover - fallback when package missing
    from .customs_calculator import CustomsCalculator


def calculate_customs(
    *,
    price_eur: float,
    engine_cc: int,
    year: int,
    car_type: str,
    power_hp: float = 0,
    weight_kg: float = 0,
    eur_rate: float | None = None,
    tariffs: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    """Return a detailed customs payment breakdown in euros.

    This is a light-weight reimplementation of the public API exposed by the
    optional :mod:`tks_api_official` package.  Only the fields required by the
    tests are computed which keeps the function intentionally simple.
    """

    tariffs = tariffs or CustomsCalculator.get_tariffs()
    eur_rate = eur_rate if eur_rate is not None else 1.0

    age = datetime.now().year - year

    duty_cfg = tariffs["duty"]
    if age < 3:
        under3 = duty_cfg["under_3"]
        duty = max(price_eur * under3["price_percent"], engine_cc * under3["per_cc"])
    elif age <= 5:
        for limit, rate in duty_cfg["3_5"]:
            if engine_cc <= limit:
                duty = engine_cc * rate
                break
    else:
        for limit, rate in duty_cfg["over_5"]:
            if engine_cc <= limit:
                duty = engine_cc * rate
                break

    excise_rub_rate = tariffs.get("excise", {}).get("over_3000_hp_rub", 0)
    excise_rub = power_hp * excise_rub_rate if power_hp > 300 else 0
    excise = excise_rub / eur_rate

    util_key = "age_under_3" if age < 3 else "age_over_3"
    utilization = tariffs["utilization"][util_key]

    processing_fee = tariffs.get("processing_fee", 0)

    vat_base = price_eur + duty + excise + utilization
    vat = 0.20 * vat_base

    total = duty + excise + utilization + processing_fee + vat

    return {
        "duty_eur": duty,
        "excise_eur": excise,
        "utilization_eur": utilization,
        "processing_fee_eur": processing_fee,
        "vat_eur": vat,
        "total_eur": total,
    }


def calculate_etc(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_etc`."""
    return CustomsCalculator.calculate_etc(*args, **kwargs)


def calculate_ctp(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_ctp`."""
    return CustomsCalculator.calculate_ctp(*args, **kwargs)


__all__ = [
    "calculate_customs",
    "calculate_etc",
    "calculate_ctp",
    "CustomsCalculator",
]
