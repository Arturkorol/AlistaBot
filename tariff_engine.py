"""Pure math utilities for HS 8703 23 908 9 customs calculations.

The module exposes helpers to compute import duty, excise, VAT and a full
breakdown for used passenger cars with engine displacement 2300–3000 cm³.
All monetary results are rounded to two decimals. Validation errors are
reported in Russian for clarity.
"""

from __future__ import annotations

from pprint import pprint
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXCISE_TABLE: List[Tuple[int, int]] = [
    (90, 0),
    (150, 61),
    (200, 583),
    (300, 955),
    (400, 1628),
    (500, 1685),
]

DEFAULT_MIN_EUR_PER_CC = 0.44
DEFAULT_AD_VALOREM = 0.20
VAT_RATE = 0.20


# ---------------------------------------------------------------------------
# Excise
# ---------------------------------------------------------------------------


def get_excise_rate_rub_per_hp(engine_hp: int) -> int:
    """Return the excise rate in RUB per horsepower.

    Parameters
    ----------
    engine_hp: int
        Engine power in horsepower. Must be within realistic bounds.
    """

    if engine_hp <= 0:
        raise ValueError("Мощность двигателя должна быть > 0 л.с.")
    if engine_hp > 2000:
        raise ValueError("Нереалистичная мощность двигателя")

    for threshold, rate in EXCISE_TABLE:
        if engine_hp <= threshold:
            return rate
    return 1740


# ---------------------------------------------------------------------------
# Duty and currency conversion
# ---------------------------------------------------------------------------


def calc_import_duty_eur(
    customs_value_eur: float,
    engine_cc: int,
    *,
    min_eur_per_cc: float = DEFAULT_MIN_EUR_PER_CC,
    ad_valorem: float = DEFAULT_AD_VALOREM,
) -> float:
    """Calculate import duty in euros.

    Duty equals max(ad_valorem * customs value, min_eur_per_cc * engine_cc).
    """

    if customs_value_eur <= 0:
        raise ValueError("Таможенная стоимость должна быть > 0 евро")
    if engine_cc <= 0 or engine_cc > 10_000:
        raise ValueError("Объём двигателя должен быть в диапазоне 1..10000 см³")
    if min_eur_per_cc < 0 or ad_valorem < 0:
        raise ValueError("Ставки пошлины должны быть неотрицательными")

    duty = max(ad_valorem * customs_value_eur, min_eur_per_cc * engine_cc)
    return round(duty, 2)


def eur_to_rub(amount_eur: float, eur_rub_rate: float) -> float:
    """Convert euros to rubles using the provided exchange rate."""

    if amount_eur < 0:
        raise ValueError("Сумма в евро не может быть отрицательной")
    if eur_rub_rate <= 0 or eur_rub_rate > 10_000:
        raise ValueError("Курс EUR/RUB должен быть в диапазоне 0..10000")
    return round(amount_eur * eur_rub_rate, 2)


# ---------------------------------------------------------------------------
# Excise and VAT helpers
# ---------------------------------------------------------------------------


def calc_excise_rub(engine_hp: int) -> float:
    """Return the excise amount in rubles for the given horsepower."""

    rate = get_excise_rate_rub_per_hp(engine_hp)
    return round(rate * engine_hp, 2)


def calc_vat_rub(
    customs_value_rub: float,
    duty_rub: float,
    excise_rub: float,
    is_disabled_vehicle: bool,
) -> float:
    """Return VAT in rubles.

    Vehicles specially equipped for disabled persons are exempt from VAT.
    """

    for value, name in (
        (customs_value_rub, "таможенная стоимость"),
        (duty_rub, "пошлина"),
        (excise_rub, "акциз"),
    ):
        if value < 0:
            raise ValueError(f"{name.capitalize()} не может быть отрицательной")

    if is_disabled_vehicle:
        return 0.0

    vat = (customs_value_rub + duty_rub + excise_rub) * VAT_RATE
    return round(vat, 2)


# ---------------------------------------------------------------------------
# Main breakdown function
# ---------------------------------------------------------------------------


def calc_import_breakdown(
    *,
    customs_value_eur: float,
    eur_rub_rate: float,
    engine_cc: int,
    engine_hp: int,
    is_disabled_vehicle: bool,
    is_export: bool,
    person_type: str = "individual",
    country_origin: str | None = None,
) -> Dict[str, Any]:
    """Return a detailed cost breakdown for vehicle import."""

    if person_type not in {"individual", "company"}:
        raise ValueError("person_type должен быть 'individual' или 'company'")
    if customs_value_eur <= 0:
        raise ValueError("Таможенная стоимость должна быть > 0 евро")
    if eur_rub_rate <= 0 or eur_rub_rate > 10_000:
        raise ValueError("Курс EUR/RUB должен быть в диапазоне 0..10000")
    if engine_cc <= 0 or engine_cc > 10_000:
        raise ValueError("Объём двигателя должен быть в диапазоне 1..10000 см³")
    if engine_hp <= 0 or engine_hp > 2000:
        raise ValueError("Мощность двигателя должна быть в диапазоне 1..2000 л.с.")

    customs_value_rub = eur_to_rub(customs_value_eur, eur_rub_rate)

    if is_export:
        duty_eur = duty_rub = excise_rub = vat_rub = 0.0
        excise_rate = 0
        vat_rate = 0.0
    else:
        duty_eur = calc_import_duty_eur(customs_value_eur, engine_cc)
        duty_rub = eur_to_rub(duty_eur, eur_rub_rate)
        excise_rub = calc_excise_rub(engine_hp)
        vat_rub = calc_vat_rub(customs_value_rub, duty_rub, excise_rub, is_disabled_vehicle)
        excise_rate = get_excise_rate_rub_per_hp(engine_hp)
        vat_rate = 0.0 if is_disabled_vehicle else VAT_RATE

    total_rub = round(customs_value_rub + duty_rub + excise_rub + vat_rub, 2)

    notes = [
        "Основы — Alta: пошлина max(20% стоимости или 0.44 EUR/см³), акциз по шкале, НДС 20% или 0%.",
        "Экспортный режим даёт пошлину/акциз/НДС 0.",
        "Тип лица не влияет на ставки (исключение — НДС 0% для спец. авто для инвалидов).",
    ]
    if is_export:
        notes.append("В данном расчёте применён экспорт: все начисления 0.")
    if is_disabled_vehicle and not is_export:
        notes.append("Автомобиль оборудован для инвалидов: применена ставка НДС 0%.")

    return {
        "inputs": {
            "customs_value_eur": customs_value_eur,
            "eur_rub_rate": eur_rub_rate,
            "engine_cc": engine_cc,
            "engine_hp": engine_hp,
            "is_disabled_vehicle": is_disabled_vehicle,
            "is_export": is_export,
            "person_type": person_type,
            "country_origin": country_origin,
        },
        "breakdown": {
            "customs_value_rub": customs_value_rub,
            "duty_eur": duty_eur,
            "duty_rub": duty_rub,
            "excise_rub": excise_rub,
            "vat_rub": vat_rub,
            "total_rub": total_rub,
        },
        "rates_used": {
            "min_eur_per_cc": DEFAULT_MIN_EUR_PER_CC,
            "ad_valorem": DEFAULT_AD_VALOREM,
            "excise_rate_rub_per_hp": excise_rate,
            "vat_rate": vat_rate,
            "eur_rub_rate": eur_rub_rate,
        },
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Demo: стандартный импорт")
    pprint(
        calc_import_breakdown(
            customs_value_eur=12000,
            eur_rub_rate=98.5,
            engine_cc=2500,
            engine_hp=200,
            is_disabled_vehicle=False,
            is_export=False,
        )
    )

    print("\nDemo: автомобиль для инвалидов")
    pprint(
        calc_import_breakdown(
            customs_value_eur=8000,
            eur_rub_rate=99.1,
            engine_cc=1800,
            engine_hp=120,
            is_disabled_vehicle=True,
            is_export=False,
        )
    )

    print("\nDemo: экспорт")
    pprint(
        calc_import_breakdown(
            customs_value_eur=15000,
            eur_rub_rate=101.3,
            engine_cc=2800,
            engine_hp=240,
            is_disabled_vehicle=False,
            is_export=True,
        )
    )
