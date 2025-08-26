"""Tariff calculation engine for HS 8703 23 908 9 vehicles.

This module provides pure mathematical utilities to calculate Russian
customs payments for used passenger cars with engine volume between
2300 and 3000 cm³ (HS 8703 23 908 9).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from bot_alista.clearance_fee import calc_clearance_fee_rub
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
from .util_fee import calc_util_rub, load_util_config

ENGINE_CC_MIN = 2300
ENGINE_CC_MAX = 3000
AD_VALOREM_RATE = 0.20
VAT_RATE = 0.20

# Preferential duty rates by country of origin.
# Values override the default ad valorem rate when applicable.
PREFERENTIAL_RATES: dict[str, dict[str, float]] = {
    "Belarus": {"ad_valorem": 0.15},
    "Kazakhstan": {"ad_valorem": 0.15},
}


def _round_currency(value: float) -> float:
    """Round monetary values using ``Decimal`` half-up to two decimals."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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
    ad_valorem: float = AD_VALOREM_RATE,
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
    if not ENGINE_CC_MIN <= engine_cc <= ENGINE_CC_MAX:
        raise ValueError(
            f"Объем двигателя должен быть в диапазоне {ENGINE_CC_MIN}–{ENGINE_CC_MAX} см³"
        )
    _validate_positive_float(min_eur_per_cc, "Ставка EUR/см³")
    _validate_positive_float(ad_valorem, "Адвалорная ставка")

    duty_cc = engine_cc * min_eur_per_cc
    duty_ad = customs_value_eur * ad_valorem
    duty = max(duty_cc, duty_ad)
    return _round_currency(duty)


def eur_to_rub(amount_eur: float, eur_rub_rate: float) -> float:
    """Конвертирует сумму из евро в рубли."""

    if amount_eur < 0:
        raise ValueError("Сумма в евро не может быть отрицательной")
    _validate_positive_float(eur_rub_rate, "Курс EUR/RUB")
    return _round_currency(amount_eur * eur_rub_rate)


def calc_excise_rub(engine_hp: int, rate: int | None = None) -> float:
    """Рассчитывает сумму акциза в рублях."""

    _validate_positive_int(engine_hp, "Мощность двигателя")
    rate = rate if rate is not None else get_excise_rate_rub_per_hp(engine_hp)
    return _round_currency(rate * engine_hp)


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
    vat = vat_base * VAT_RATE
    return _round_currency(vat)


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
) -> dict[str, Any]:
    """Полный расчет таможенных платежей при импорте.

    Возвращает словарь со структурой:
        {
            "inputs": {...},
            "breakdown": {
                ... duty/excise/vat ...,
                "clearance_fee_rub": ..., "util_rub": ..., "total_rub": ...
            },
            "rates_used": {...},
            "notes": [str, ...]
        }
    """

    _validate_positive_float(customs_value_eur, "Таможенная стоимость")
    _validate_positive_float(eur_rub_rate, "Курс EUR/RUB")
    _validate_positive_int(engine_cc, "Объем двигателя")
    if not ENGINE_CC_MIN <= engine_cc <= ENGINE_CC_MAX:
        raise ValueError(
            f"Объем двигателя должен быть в диапазоне {ENGINE_CC_MIN}–{ENGINE_CC_MAX} см³"
        )
    _validate_positive_int(engine_hp, "Мощность двигателя")

    customs_value_rub = eur_to_rub(customs_value_eur, eur_rub_rate)

    pref = PREFERENTIAL_RATES.get(country_origin or "")
    ad_val = pref.get("ad_valorem", AD_VALOREM_RATE) if pref else AD_VALOREM_RATE

    clearance_fee_rub = 0.0
    util_rub = 0.0

    if is_export:
        duty_eur = 0.0
        duty_rub = 0.0
        excise_rub = 0.0
        vat_rub = 0.0
        excise_rate = 0
        vat_rate = 0.0
    else:
        duty_eur = calc_import_duty_eur(
            customs_value_eur, engine_cc, ad_valorem=ad_val
        )
        duty_rub = eur_to_rub(duty_eur, eur_rub_rate)
        excise_rate = get_excise_rate_rub_per_hp(engine_hp)
        excise_rub = calc_excise_rub(engine_hp, excise_rate)
        vat_rate = 0.0 if is_disabled_vehicle else VAT_RATE
        vat_rub = calc_vat_rub(
            customs_value_rub, duty_rub, excise_rub, is_disabled_vehicle
        )
        clearance_fee_rub = calc_clearance_fee_rub(customs_value_rub)
        util_rub = calc_util_rub(
            person_type=person_type,
            usage="personal" if person_type == "individual" else "commercial",
            engine_cc=engine_cc,
            fuel="ice",
            vehicle_kind="passenger",
            age_years=0.0,
            date_decl=date.today(),
            avg_vehicle_cost_rub=0.0,
            actual_costs_rub=0.0,
            config=load_util_config(),
        )

    total_rub = _round_currency(
        duty_rub + excise_rub + vat_rub + clearance_fee_rub + util_rub
    )

    result: dict[str, Any] = {
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
            "clearance_fee_rub": clearance_fee_rub,
            "util_rub": util_rub,
            "total_rub": total_rub,
        },
        "rates_used": {
            "duty_min_eur_per_cc": 0.44,
            "duty_ad_valorem": ad_val,
            "excise_rate_rub_per_hp": excise_rate,
            "vat_rate": vat_rate,
        },
        "notes": [
            "Альта: пошлина — максимум 20% от стоимости или 0.44 EUR/см³; "
            "акциз — по шкале мощности; НДС — 20% от суммы, 0% для "
            "авто, оборудованных для инвалидов; включены таможенный "
            "сбор и утильсбор.",
            "При экспорте пошлина, акциз, сборы и НДС не начисляются.",
            "Тип лица не влияет на ставки (кроме НДС 0% для спецавто для инвалидов).",
        ],
    }

    if pref:
        result["notes"].append(
            f"Применена преференция для страны происхождения {country_origin}"
        )

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
    fuel_type: str,
    decl_date: date,
) -> dict:
    """Compatibility wrapper that delegates to :func:`calc_breakdown_rules`.

    Previous versions implemented two separate calculation paths.  The logic
    is now unified via the rule-based engine.
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
            country_origin=None,
        )
        return core

    years = int(age_years)
    months = int((age_years - years) * 12)
    production_year = decl_date.year - years
    if decl_date.month - months <= 0:
        production_year -= 1
    result = calc_breakdown_rules(
        person_type=person_type,
        usage_type=usage_type,
        customs_value_eur=customs_value_eur,
        eur_rub_rate=eur_rub_rate,
        engine_cc=engine_cc,
        engine_hp=engine_hp,
        production_year=production_year,
        age_choice_over3=age_years > 3,
        fuel_type=fuel_type,
        decl_date=decl_date,
    )

    if is_disabled_vehicle:
        br = result["breakdown"]
        removed = br.get("vat_rub", 0.0)
        br["vat_rub"] = 0.0
        br["total_rub"] = _round_currency(br["total_rub"] - removed)
        if "total_with_util_rub" in br:
            br["total_with_util_rub"] = _round_currency(
                br["total_with_util_rub"] - removed
            )
        result.setdefault("notes", []).append(
            "VAT waived for disabled vehicle."
        )

    return result


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
    if engine_cc is None:
        raise ValueError("engine_cc is required")
    _validate_positive_int(engine_cc, "Объем двигателя")

    if person_type != "individual" or usage_type != "personal":
        if engine_hp is None:
            raise ValueError("engine_hp is required")
        _validate_positive_int(engine_hp, "Мощность двигателя")
    elif engine_hp is not None:
        _validate_positive_int(engine_hp, "Мощность двигателя")

    fuel_norm = normalize_fuel_label(fuel_type)
    rules, labels, buckets = _get_rule_env()

    util_fuel = (
        "ev" if fuel_norm == "Электро" else "hybrid" if fuel_norm == "Гибрид" else "ice"
    )

    customs_value_rub = _round_currency(customs_value_eur * eur_rub_rate)
    actual_age = compute_actual_age_years(production_year, decl_date)

    if person_type == "individual" and usage_type == "personal":
        # Resolve FL age label with graceful fallback
        fl_age_candidates = candidate_fl_labels(age_choice_over3, actual_age, buckets)
        last_exc: Exception | None = None
        core = None
        fl_age_label = fl_age_candidates[0]
        fallback_used = False
        for label in fl_age_candidates:
            try:
                core = calc_fl_stp(
                    rules=rules,
                    customs_value_eur=customs_value_eur,
                    eur_rub_rate=eur_rub_rate,
                    engine_cc=engine_cc,
                    segment=segment, category=category,
                    fuel=fuel_norm, age_bucket=label,
                )
                fl_age_label = label
                if label != fl_age_candidates[0]:
                    fallback_used = True
                break
            except Exception as exc:
                last_exc = exc
        if core is None:
            raise last_exc or ValueError("No applicable FL rule found")
        fee_rub = calc_clearance_fee_rub(customs_value_rub)
        total_no_util = _round_currency(core["duty_rub"] + fee_rub)

        # UTIL uses factual age directly
        util_rub = calc_util_rub(
            person_type="individual",
            usage="personal",
            engine_cc=engine_cc,
            fuel=util_fuel,
            vehicle_kind="passenger",
            age_years=actual_age,
            date_decl=decl_date,
            avg_vehicle_cost_rub=None,
            actual_costs_rub=None,
            config=load_util_config(),
        )
        total_with_util = _round_currency(total_no_util + util_rub)

        result = {
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

        if fallback_used:
            result.setdefault("notes", []).append(
                f"⚠️ age bucket fallback: {fl_age_candidates[0]}→{fl_age_label}"
            )

        return result

    # UL / commercial — always factual age mapping with fallback
    ul_age_candidates = candidate_ul_labels(actual_age, buckets)
    last_exc = None
    core = None
    ul_age_label = ul_age_candidates[0]
    ul_fallback_used = False
    for label in ul_age_candidates:
        try:
            core = calc_ul(
                rules=rules,
                customs_value_eur=customs_value_eur,
                eur_rub_rate=eur_rub_rate,
                engine_cc=engine_cc,
                engine_hp=engine_hp,
                segment=segment, category=category,
                fuel=fuel_norm, age_bucket=label,
            )
            ul_age_label = label
            if label != ul_age_candidates[0]:
                ul_fallback_used = True
            break
        except Exception as exc:
            last_exc = exc
    if core is None:
        raise last_exc or ValueError("No applicable UL rule found")

    fee_rub = calc_clearance_fee_rub(customs_value_rub)
    total_no_util = _round_currency(core["duty_rub"] + core["excise_rub"] + core["vat_rub"] + fee_rub)

    util_rub = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=engine_cc,
        fuel=util_fuel,
        vehicle_kind="passenger",
        age_years=actual_age,
        date_decl=decl_date,
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=load_util_config(),
    )
    total_with_util = _round_currency(total_no_util + util_rub)

    result = {
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

    if ul_fallback_used:
        result.setdefault("notes", []).append(
            f"⚠️ age bucket fallback: {ul_age_candidates[0]}→{ul_age_label}"
        )

    return result


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
