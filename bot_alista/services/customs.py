from __future__ import annotations

from typing import Dict

try:
    from tks_api_official import CustomsCalculator
except ImportError:  # pragma: no cover - fallback when package missing
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
) -> Dict[str, float]:
    """Proxy to :class:`CustomsCalculator.calculate_customs`.

    The helper returns a simplified dictionary compatible with the previous
    interface used in tests.
    """

    res = CustomsCalculator.calculate_customs(
        price_eur=price_eur,
        engine_cc=engine_cc,
        year=year,
        car_type=car_type,
        power_hp=power_hp,
        weight_kg=weight_kg,
        eur_rate=eur_rate,
    )
    return {
        "duty_eur": res["duty_eur"],
        "utilization_eur": res["util_eur"],
        "vat_eur": res["vat_eur"],
        "processing_fee_eur": res["fee_eur"],
        "total_eur": res["total_eur"],
    }


def calculate_etc(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_etc`."""
    return CustomsCalculator.calculate_etc(*args, **kwargs)


def calculate_ctp(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_ctp`."""
    return CustomsCalculator.calculate_ctp(*args, **kwargs)


__all__ = ["calculate_customs", "calculate_etc", "calculate_ctp", "CustomsCalculator"]
