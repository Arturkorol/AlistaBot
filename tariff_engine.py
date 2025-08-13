"""Tariff calculation engine for HS 8703 23 908 9 vehicles.

This module provides pure mathematical utilities to calculate Russian
customs payments for used passenger cars with engine volume between
2300 and 3000 cm³ (HS 8703 23 908 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from bot_alista.tariff.personal_rates import (
    calc_individual_personal_duty_eur,
    CUSTOMS_CLEARANCE_FEE_RUB,
)


@dataclass(frozen=True)
class ExciseBracket:
    max_hp: int | None
    rate: int


EXCISE_BRACKETS: tuple[ExciseBracket, ...] = (
    ExciseBracket(max_hp=90, rate=0),
    ExciseBracket(max_hp=150, rate=61),
    ExciseBracket(max_hp=200, rate=583),
    ExciseBracket(max_hp=300, rate=955),
    ExciseBracket(max_hp=400, rate=1628),
    ExciseBracket(max_hp=500, rate=1685),
    ExciseBracket(max_hp=None, rate=1740),
)


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} должен быть положительным целым числом")


def _validate_positive_float(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} должно быть положительным числом")


# Public API ---------------------------------------------------------------


def get_excise_rate_rub_per_hp(engine_hp: int) -> int:
    """Возвращает ставку акциза (руб/л.с.) по мощности двигателя.

    Parameters
    ----------
    engine_hp : int
        Мощность двигателя в лошадиных силах.

    Returns
    -------
    int
        Ставка акциза в рублях за одну лошадиную силу.

    Raises
    ------
    ValueError
        Если мощность не положительна.
    """

    _validate_positive_int(engine_hp, "Мощность двигателя")
    for bracket in EXCISE_BRACKETS:
        if bracket.max_hp is None or engine_hp <= bracket.max_hp:
            return bracket.rate
    # Unreachable
    raise RuntimeError("Не удалось определить ставку акциза")


def calc_import_duty_eur(
    customs_value_eur: float,
    engine_cc: int,
    *,
    min_eur_per_cc: float = 0.44,
    ad_valorem: float = 0.20,
) -> float:
    """Рассчитывает ввозную пошлину в евро.

    Пошлина равна максимуму между адвалорной ставкой и ставкой за кубический
    сантиметр.

    Parameters
    ----------
    customs_value_eur : float
        Таможенная стоимость автомобиля в евро.
    engine_cc : int
        Объем двигателя в см³ (должен быть в диапазоне 2300–3000).
    min_eur_per_cc : float, optional
        Минимальная ставка в евро за см³, по умолчанию 0.44.
    ad_valorem : float, optional
        Адвалорная ставка, доля от стоимости, по умолчанию 0.20.

    Returns
    -------
    float
        Размер пошлины в евро, округленный до двух знаков после запятой.
    """

    _validate_positive_float(customs_value_eur, "Таможенная стоимость")
    _validate_positive_int(engine_cc, "Объем двигателя")
    if not 2300 <= engine_cc <= 3000:
        raise ValueError("Объем двигателя должен быть в диапазоне 2300–3000 см³")
    _validate_positive_float(min_eur_per_cc, "Ставка EUR/см³")
    _validate_positive_float(ad_valorem, "Адвалорная ставка")

    duty_cc = engine_cc * min_eur_per_cc
    duty_ad = customs_value_eur * ad_valorem
    duty = max(duty_cc, duty_ad)
    return round(duty, 2)


def eur_to_rub(amount_eur: float, eur_rub_rate: float) -> float:
    """Конвертирует сумму из евро в рубли."""

    if amount_eur < 0:
        raise ValueError("Сумма в евро не может быть отрицательной")
    _validate_positive_float(eur_rub_rate, "Курс EUR/RUB")
    return round(amount_eur * eur_rub_rate, 2)


def calc_excise_rub(engine_hp: int) -> float:
    """Рассчитывает сумму акциза в рублях."""

    rate = get_excise_rate_rub_per_hp(engine_hp)
    excise = rate * engine_hp
    return round(float(excise), 2)


def calc_vat_rub(
    customs_value_rub: float,
    duty_rub: float,
    excise_rub: float,
    is_disabled_vehicle: bool,
) -> float:
    """Вычисляет НДС в рублях."""

    for value, name in (
        (customs_value_rub, "Таможенная стоимость"),
        (duty_rub, "Пошлина"),
        (excise_rub, "Акциз"),
    ):
        if value < 0:
            raise ValueError(f"{name} не может быть отрицательной")

    if is_disabled_vehicle:
        return 0.0

    vat_base = customs_value_rub + duty_rub + excise_rub
    vat = vat_base * 0.20
    return round(vat, 2)


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
    """Полный расчет таможенных платежей при импорте.

    Returns словарь со структурой:
        {
            "inputs": {...},
            "breakdown": {...},
            "rates_used": {...},
            "notes": [str, ...]
        }
    """

    _validate_positive_float(customs_value_eur, "Таможенная стоимость")
    _validate_positive_float(eur_rub_rate, "Курс EUR/RUB")
    _validate_positive_int(engine_cc, "Объем двигателя")
    if not 2300 <= engine_cc <= 3000:
        raise ValueError("Объем двигателя должен быть в диапазоне 2300–3000 см³")
    _validate_positive_int(engine_hp, "Мощность двигателя")

    customs_value_rub = eur_to_rub(customs_value_eur, eur_rub_rate)

    if is_export:
        duty_eur = 0.0
        duty_rub = 0.0
        excise_rub = 0.0
        vat_rub = 0.0
        excise_rate = 0
        vat_rate = 0.0
    else:
        duty_eur = calc_import_duty_eur(customs_value_eur, engine_cc)
        duty_rub = eur_to_rub(duty_eur, eur_rub_rate)
        excise_rate = get_excise_rate_rub_per_hp(engine_hp)
        excise_rub = calc_excise_rub(engine_hp)
        vat_rate = 0.0 if is_disabled_vehicle else 0.20
        vat_rub = calc_vat_rub(customs_value_rub, duty_rub, excise_rub, is_disabled_vehicle)

    total_rub = round(duty_rub + excise_rub + vat_rub, 2)

    result: Dict[str, Any] = {
        "inputs": {
            "customs_value_eur": round(customs_value_eur, 2),
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
            "duty_min_eur_per_cc": 0.44,
            "duty_ad_valorem": 0.20,
            "excise_rate_rub_per_hp": excise_rate,
            "vat_rate": vat_rate,
        },
        "notes": [
            "Альта: пошлина — максимум 20% от стоимости или 0.44 EUR/см³; "
            "акциз — по шкале мощности; НДС — 20% от суммы, 0% для "
            "авто, оборудованных для инвалидов.",
            "При экспорте пошлина, акциз и НДС не начисляются.",
            "Тип лица не влияет на ставки (кроме НДС 0% для спецавто для инвалидов).",
        ],
    }

    return result


def calc_individual_personal_breakdown(*, engine_cc: int, age_years: float, eur_rub_rate: float) -> dict:
    """
    Individuals (personal use):
      - duty by EUR/cc table (no VAT, no excise)
      - + customs clearance fee (RUB)
    Returns a dict with duty_eur/duty_rub, excise_rub=0, vat_rub=0, clearance_fee_rub.
    """
    duty_eur = calc_individual_personal_duty_eur(engine_cc, age_years)
    duty_rub = round(duty_eur * eur_rub_rate, 2)
    return {
        "duty_eur": duty_eur,
        "duty_rub": duty_rub,
        "excise_rub": 0.0,
        "vat_rub": 0.0,
        "clearance_fee_rub": float(CUSTOMS_CLEARANCE_FEE_RUB),
    }


def calc_breakdown_with_mode(
    *,
    person_type: str,
    usage_type: str,
    customs_value_eur: float,
    eur_rub_rate: float,
    engine_cc: int,
    engine_hp: int,
    age_years: float,
    is_disabled_vehicle: bool,
    is_export: bool,
) -> dict:
    """
    Unified entry:
    - Individuals + personal use -> per-cc table (no VAT, no excise) + clearance fee.
    - Else (companies/commercial) -> Alta: duty = max(20% of EUR value, 0.44 EUR/cc) + excise + VAT.
    Returns a dict like calc_import_breakdown, with total_rub (NO util fee).
    """
    if is_export:
        core = calc_import_breakdown(
            customs_value_eur=customs_value_eur,
            eur_rub_rate=eur_rub_rate,
            engine_cc=engine_cc,
            engine_hp=engine_hp,
            is_disabled_vehicle=is_disabled_vehicle,
            is_export=True,
            person_type=person_type,
        )
        core["breakdown"]["clearance_fee_rub"] = 0.0
        return core

    if person_type == "individual" and usage_type == "personal":
        core = calc_individual_personal_breakdown(
            engine_cc=engine_cc,
            age_years=age_years,
            eur_rub_rate=eur_rub_rate,
        )
        customs_value_rub = round(customs_value_eur * eur_rub_rate, 2)
        total_rub = round(
            core["duty_rub"]
            + core["excise_rub"]
            + core["vat_rub"]
            + core["clearance_fee_rub"],
            2,
        )
        return {
            "inputs": {
                "person_type": person_type,
                "usage_type": usage_type,
                "engine_cc": engine_cc,
                "engine_hp": engine_hp,
                "age_years": age_years,
                "eur_rub_rate": eur_rub_rate,
                "customs_value_eur": customs_value_eur,
                "is_disabled_vehicle": is_disabled_vehicle,
                "is_export": False,
            },
            "breakdown": {
                "customs_value_rub": customs_value_rub,
                **core,
                "total_rub": total_rub,
            },
            "rates_used": {
                "mode": "individual_personal_rate_table",
                "clearance_fee_rub": core["clearance_fee_rub"],
                "note": "No VAT/excise for the individual personal table.",
            },
            "notes": [
                "Individual (personal use): duty by per-cc age×cc table (EUR/cc).",
                "No VAT, no excise; customs clearance fee added.",
            ],
        }

    corp = calc_import_breakdown(
        customs_value_eur=customs_value_eur,
        eur_rub_rate=eur_rub_rate,
        engine_cc=engine_cc,
        engine_hp=engine_hp,
        is_disabled_vehicle=is_disabled_vehicle,
        is_export=False,
        person_type=person_type,
    )
    corp["breakdown"].setdefault("clearance_fee_rub", 0.0)
    corp.setdefault("rates_used", {}).update({"mode": "corporate_alta"})
    corp.setdefault("notes", []).append(
        "Company/commercial mode: Alta rules (20% vs ≥0.44 EUR/cc) + excise + VAT."
    )
    return corp


if __name__ == "__main__":
    demo1 = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=False,
        is_export=False,
    )
    print("Demo 1:", demo1)

    demo2 = calc_import_breakdown(
        customs_value_eur=15000,
        eur_rub_rate=95,
        engine_cc=2800,
        engine_hp=220,
        is_disabled_vehicle=True,
        is_export=False,
    )
    print("Demo 2:", demo2)

    demo3 = calc_import_breakdown(
        customs_value_eur=20000,
        eur_rub_rate=90,
        engine_cc=3000,
        engine_hp=250,
        is_disabled_vehicle=False,
        is_export=True,
    )
    print("Demo 3 (export):", demo3)
