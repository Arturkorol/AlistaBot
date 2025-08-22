from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

try:
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
    """Простейший расчёт таможенных платежей в евро.

    Функция покрывает минимальный набор сценариев, необходимый для тестов.
    Она учитывает пошлину, утилизационный сбор, НДС и сбор за оформление.
    """

    tariffs = tariffs or CustomsCalculator.get_tariffs()
    age = datetime.now().year - year

    if age < 3:
        duty_cfg = tariffs["duty"]["under_3"]
        duty = max(price_eur * duty_cfg["price_percent"], engine_cc * duty_cfg["per_cc"])
        util = tariffs["utilization"]["age_under_3"]
    else:
        table_key = "3_5" if age <= 5 else "over_5"
        table = tariffs["duty"][table_key]
        rate = 0.0
        for max_cc, r in table:
            if engine_cc <= max_cc:
                rate = r
                break
        duty = engine_cc * rate
        util = tariffs["utilization"]["age_over_3"]

    vat = (price_eur + duty + util) * 0.20
    fee = tariffs["processing_fee"]
    total = duty + util + vat + fee

    return {
        "duty_eur": duty,
        "utilization_eur": util,
        "vat_eur": vat,
        "processing_fee_eur": fee,
        "total_eur": total,
    }


def calculate_etc(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_etc`."""
    return CustomsCalculator.calculate_etc(*args, **kwargs)


def calculate_ctp(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_ctp`."""
    return CustomsCalculator.calculate_ctp(*args, **kwargs)


__all__ = ["calculate_customs", "calculate_etc", "calculate_ctp", "CustomsCalculator"]
