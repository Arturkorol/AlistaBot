"""Tariff calculation engine for HS 8703 23 908 9 vehicles.

This module provides pure mathematical utilities to calculate Russian
customs payments for used passenger cars with engine volume between
2300 and 3000 cm³ (HS 8703 23 908 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict
from datetime import date

from bot_alista.tariff.personal_rates import (
    calc_individual_personal_duty_eur,
)
from bot_alista.rules.loader import (
    load_rules,
    get_available_age_labels,
    normalize_fuel_label,
    RuleRow,
)
from bot_alista.rules.age import (
    compute_actual_age_years,
    detect_buckets,
    candidate_ul_labels,
    candidate_fl_labels,
)
from bot_alista.rules.engine import calc_fl_stp, calc_ul
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG


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


@lru_cache(maxsize=1)
def _get_rule_env() -> tuple[list[RuleRow], set[str], tuple[str, ...]]:
    """Return cached rules along with age labels and detected buckets."""
    rules = load_rules()
    labels = get_available_age_labels(rules)
    buckets = detect_buckets(labels)
    return rules, labels, buckets


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} должен быть положительным целым числом")


def _validate_positive_float(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} должно быть положительным числом")


def calc_clearance_fee_rub(customs_value_rub: float) -> float:
    """
    Customs clearance fee ladder (RUB), tuned to hit known 2025 bands:
      ~1.2M → 4,269 ; ~2.4M → 11,746 ; ~4.0M → 16,524
    Extend as needed for higher tiers.
    """
    v = float(customs_value_rub)
    if v <= 200_000:    return 1_067.0
    if v <= 450_000:    return 2_134.0
    if v <= 1_200_000:  return 4_269.0
    if v <= 3_000_000:  return 11_746.0
    if v <= 5_000_000:  return 16_524.0
    if v <= 7_000_000:  return 20_000.0
    return 30_000.0


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
        customs_value_rub = round(customs_value_eur * eur_rub_rate, 2)

        core = {
            "duty_eur": calc_individual_personal_duty_eur(engine_cc, age_years),
        }
        core["duty_rub"] = round(core["duty_eur"] * eur_rub_rate, 2)
        core["excise_rub"] = 0.0
        core["vat_rub"] = 0.0
        core["clearance_fee_rub"] = calc_clearance_fee_rub(customs_value_rub)

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
                "note": "No VAT/excise for individual/personal table; clearance fee is tiered.",
            },
            "notes": [
                "Individual (personal use): duty by per-cc age×cc table (EUR/cc).",
                "No VAT, no excise; tiered customs clearance fee applied.",
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


def calc_breakdown_rules(
    *,
    person_type: str,          # "individual" | "company"
    usage_type: str,           # "personal"  | "commercial"
    customs_value_eur: float,
    eur_rub_rate: float,
    engine_cc: int | None,
    engine_hp: int | None,
    production_year: int,
    age_choice_over3: bool,    # FL: user's answer to "older than 3?"
    fuel_type: str,
    decl_date: date | None,
    segment: str = "Легковой",
    category: str = "M1",
) -> dict:

    decl_date = decl_date or date.today()
    fuel_norm = normalize_fuel_label(fuel_type)
    rules, labels, buckets = _get_rule_env()

    customs_value_rub = round(customs_value_eur * eur_rub_rate, 2)
    actual_age = compute_actual_age_years(production_year, decl_date)

    if person_type == "individual" and usage_type == "personal":
        # Resolve FL age label with graceful fallback
        fl_age_candidates = candidate_fl_labels(age_choice_over3, actual_age, buckets)
        last_exc: Exception | None = None
        core = None
        fl_age_label = fl_age_candidates[0]
        for label in fl_age_candidates:
            try:
                core = calc_fl_stp(
                    rules=rules,
                    customs_value_eur=customs_value_eur,
                    eur_rub_rate=eur_rub_rate,
                    engine_cc=int(engine_cc or 0),
                    segment=segment, category=category,
                    fuel=fuel_norm, age_bucket=label,
                )
                fl_age_label = label
                break
            except Exception as exc:
                last_exc = exc
        if core is None:
            raise last_exc or ValueError("No applicable FL rule found")
        fee_rub = calc_clearance_fee_rub(customs_value_rub)
        total_no_util = round(core["duty_rub"] + fee_rub, 2)

        # UTIL uses factual age (not the user's button)
        util_age_years = 4.0 if actual_age > 3.0 else 2.0
        util_rub = calc_util_rub(
            person_type="individual",
            usage="personal",
            engine_cc=int(engine_cc or 0),
            fuel=("ev" if fuel_norm == "Электро" else "ice"),
            vehicle_kind="passenger",
            age_years=util_age_years,
            date_decl=decl_date,
            avg_vehicle_cost_rub=None,
            actual_costs_rub=None,
            config=UTIL_CONFIG,
        )
        total_with_util = round(total_no_util + util_rub, 2)

        return {
            "inputs": {
                "person_type": person_type, "usage_type": usage_type,
                "engine_cc": engine_cc, "engine_hp": engine_hp,
                "production_year": production_year,
                "age_choice_over3": age_choice_over3,
                "fuel_type": fuel_norm,
                "decl_date": decl_date.isoformat(),
                "eur_rub_rate": eur_rub_rate,
                "customs_value_eur": customs_value_eur,
            },
            "breakdown": {
                "customs_value_rub": customs_value_rub,
                "duty_eur": core["duty_eur"],
                "duty_rub": core["duty_rub"],
                "excise_rub": core["excise_rub"],
                "vat_rub": core["vat_rub"],
                "clearance_fee_rub": fee_rub,
                "total_rub": total_no_util,
                "util_rub": util_rub,
                "total_with_util_rub": total_with_util,
            },
            "notes": [
                f"FL STP by CSV: age_bucket={fl_age_label}, fuel={fuel_norm}",
                "VAT/excise embedded in STP.",
                "Util fee uses factual age (by production year).",
            ],
        }

    # UL / commercial — always factual age mapping with fallback
    ul_age_candidates = candidate_ul_labels(actual_age, buckets)
    last_exc = None
    core = None
    ul_age_label = ul_age_candidates[0]
    for label in ul_age_candidates:
        try:
            core = calc_ul(
                rules=rules,
                customs_value_eur=customs_value_eur,
                eur_rub_rate=eur_rub_rate,
                engine_cc=int(engine_cc or 0),
                engine_hp=int(engine_hp or 0),
                segment=segment, category=category,
                fuel=fuel_norm, age_bucket=label,
            )
            ul_age_label = label
            break
        except Exception as exc:
            last_exc = exc
    if core is None:
        raise last_exc or ValueError("No applicable UL rule found")

    fee_rub = calc_clearance_fee_rub(customs_value_rub)
    total_no_util = round(core["duty_rub"] + core["excise_rub"] + core["vat_rub"] + fee_rub, 2)

    util_rub = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=int(engine_cc or 0),
        fuel=("ev" if fuel_norm == "Электро" else "ice"),
        vehicle_kind="passenger",
        age_years=actual_age,
        date_decl=decl_date,
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=UTIL_CONFIG,
    )
    total_with_util = round(total_no_util + util_rub, 2)

    return {
        "inputs": {
            "person_type": person_type, "usage_type": usage_type,
            "engine_cc": engine_cc, "engine_hp": engine_hp,
            "production_year": production_year,
            "fuel_type": fuel_norm,
            "decl_date": decl_date.isoformat(),
            "eur_rub_rate": eur_rub_rate,
            "customs_value_eur": customs_value_eur,
        },
        "breakdown": {
            "customs_value_rub": customs_value_rub,
            "duty_eur": core["duty_eur"],
            "duty_rub": core["duty_rub"],
            "excise_rub": core["excise_rub"],
            "vat_rub": core["vat_rub"],
            "clearance_fee_rub": fee_rub,
            "total_rub": total_no_util,
            "util_rub": util_rub,
            "total_with_util_rub": total_with_util,
        },
        "notes": [
            f"UL by CSV: age_bucket={ul_age_label}, fuel={fuel_norm}",
            "VAT=20% unless overridden by rule; Excise = rub/hp from rules.",
            "Util fee per 2025 formula module.",
        ],
    }


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
