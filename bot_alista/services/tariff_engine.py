"""Tariff calculation engine for HS code 8703 23 908 9.

This module implements pure mathematical functions to estimate customs charges
for used passenger cars with engine displacement over 2300 cm³ and no more
than 3000 cm³ (HS code 8703239089). It reflects the rates published on the
Alta-Soft page "Код ТН ВЭД 8703239089" – import duty 20% but not less than
0.44 €/см³, excise tax scale based on engine power, VAT 20% (0% for vehicles
specially equipped for disabled persons), and zero duty/excise for export
conditions.
"""

from __future__ import annotations

from typing import Dict, Any

# Rate constants
IMPORT_DUTY_PERCENT: float = 0.20
IMPORT_DUTY_MIN_EUR_PER_CC: float = 0.44

EXCISE_SCALE_RUB_PER_HP: Dict[str, int] = {
    "<=90": 0,
    "91-150": 61,
    "151-200": 583,
    "201-300": 955,
    "301-400": 1628,
    "401-500": 1685,
    ">500": 1740,
}

VAT_PERCENT_DEFAULT: float = 0.20
VAT_PERCENT_DISABLED_VEHICLE: float = 0.0


# Helper functions

def get_excise_rate_rub_per_hp(engine_hp: int) -> int:
    """Return excise rate in RUB per horsepower based on thresholds."""
    if engine_hp <= 90:
        return EXCISE_SCALE_RUB_PER_HP["<=90"]
    if engine_hp <= 150:
        return EXCISE_SCALE_RUB_PER_HP["91-150"]
    if engine_hp <= 200:
        return EXCISE_SCALE_RUB_PER_HP["151-200"]
    if engine_hp <= 300:
        return EXCISE_SCALE_RUB_PER_HP["201-300"]
    if engine_hp <= 400:
        return EXCISE_SCALE_RUB_PER_HP["301-400"]
    if engine_hp <= 500:
        return EXCISE_SCALE_RUB_PER_HP["401-500"]
    return EXCISE_SCALE_RUB_PER_HP[">500"]


def calc_import_duty_eur(customs_value_eur: float, engine_cc: int) -> float:
    """Calculate import duty in euros."""
    duty_eur = max(customs_value_eur * IMPORT_DUTY_PERCENT,
                   engine_cc * IMPORT_DUTY_MIN_EUR_PER_CC)
    return round(duty_eur, 2)


def calc_excise_rub(engine_hp: int) -> float:
    """Calculate excise tax in rubles."""
    rate = get_excise_rate_rub_per_hp(engine_hp)
    return round(engine_hp * rate, 2)


def calc_vat_rub(
    customs_value_rub: float,
    duty_rub: float,
    excise_rub: float,
    is_disabled_vehicle: bool,
) -> float:
    """Calculate VAT in rubles."""
    percent = (
        VAT_PERCENT_DISABLED_VEHICLE
        if is_disabled_vehicle
        else VAT_PERCENT_DEFAULT
    )
    vat = percent * (customs_value_rub + duty_rub + excise_rub)
    return round(vat, 2)


def convert_eur_to_rub(amount_eur: float, eur_rub_rate: float) -> float:
    """Convert amount in EUR to RUB using given rate."""
    return round(amount_eur * eur_rub_rate, 2)


def calc_import_breakdown(
    *,
    customs_value_eur: float,
    eur_rub_rate: float,
    engine_cc: int,
    engine_hp: int,
    person_type: str,
    is_disabled_vehicle: bool,
    is_export: bool,
    country_origin: str | None = None,
) -> Dict[str, Any]:
    """Return detailed customs cost breakdown and metadata."""
    if person_type not in {"individual", "company"}:
        raise ValueError("person_type must be 'individual' or 'company'")

    notes = [
        (
            "Источник: страница Alta-Soft по коду ТН ВЭД 8703239089 (импортная "
            "пошлина 20% или минимум 0.44 €/см³; шкала акцизов по мощности; "
            "НДС 20% или 0% для специальных ТС для инвалидов; экспорт — "
            "беспошлинно и без акциза)."
        ),
        (
            "По данным источника ставки одинаковы для физлиц и юрлиц; "
            "различие — НДС=0% для специальных ТС для инвалидов."
        ),
        (
            "Ставки на странице показаны для Китая; для других стран "
            "происхождения ставки уточняются в 'Такса онлайн'."
        ),
    ]

    if is_export:
        notes.append("Экспорт — беспошлинно, без акциза.")
        breakdown = {
            "customs_value_rub": 0.0,
            "duty_eur": 0.0,
            "duty_rub": 0.0,
            "excise_rub": 0.0,
            "vat_rub": 0.0,
            "total_rub": 0.0,
        }
    else:
        customs_value_rub = convert_eur_to_rub(customs_value_eur, eur_rub_rate)
        duty_eur = calc_import_duty_eur(customs_value_eur, engine_cc)
        duty_rub = convert_eur_to_rub(duty_eur, eur_rub_rate)
        excise_rub = calc_excise_rub(engine_hp)
        vat_rub = calc_vat_rub(
            customs_value_rub, duty_rub, excise_rub, is_disabled_vehicle
        )
        total_rub = round(
            customs_value_rub + duty_rub + excise_rub + vat_rub, 2
        )
        breakdown = {
            "customs_value_rub": customs_value_rub,
            "duty_eur": duty_eur,
            "duty_rub": duty_rub,
            "excise_rub": excise_rub,
            "vat_rub": vat_rub,
            "total_rub": total_rub,
        }

    return {
        "inputs": {
            "customs_value_eur": round(customs_value_eur, 2),
            "eur_rub_rate": round(eur_rub_rate, 2),
            "engine_cc": engine_cc,
            "engine_hp": engine_hp,
            "person_type": person_type,
            "is_disabled_vehicle": is_disabled_vehicle,
            "is_export": is_export,
            "country_origin": country_origin,
        },
        "breakdown": breakdown,
        "rates_used": {
            "import_duty_percent": IMPORT_DUTY_PERCENT,
            "import_duty_min_eur_per_cc": IMPORT_DUTY_MIN_EUR_PER_CC,
            "excise_scale_rub_per_hp": EXCISE_SCALE_RUB_PER_HP,
            "vat_percent_default": VAT_PERCENT_DEFAULT,
            "vat_percent_disabled_vehicle": VAT_PERCENT_DISABLED_VEHICLE,
        },
        "notes": notes,
    }
