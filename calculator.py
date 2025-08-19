"""Расчёт таможенных платежей для импорта автомобилей в РФ.

Модуль содержит функции для вычисления полной стоимости растаможки
для физических и юридических лиц. Таблицы тарифов заданы в виде
словарей, что упрощает их актуализацию. Все сообщения и интерфейсные
подсказки представлены на русском языке.
"""
from __future__ import annotations

from datetime import date
from typing import Dict

import math

from bot_alista.services.rates import get_cached_rate_sync as get_cached_rate

# ---------------------------------------------------------------------------
# Вспомогательные структуры и таблицы тарифов
# ---------------------------------------------------------------------------

Currency = str

SUPPORTED_CURRENCIES: tuple[Currency, ...] = ("USD", "EUR", "CNY", "JPY", "RUB")


# СТП для физических лиц: проценты и минимальные ставки €/см³
# Таблицы основаны на действующих ставках 2025 года
FL_STP_UNDER3 = [
    (1000, {"pct": 0.54, "min": 2.5}),
    (1500, {"pct": 0.48, "min": 3.5}),
    (1800, {"pct": 0.48, "min": 5.5}),
    (2300, {"pct": 0.48, "min": 7.5}),
    (3000, {"pct": 0.48, "min": 15.0}),
    (math.inf, {"pct": 0.48, "min": 20.0}),
]

FL_STP_3_5 = [
    (1000, 1.5), (1500, 1.7), (1800, 2.5),
    (2300, 2.7), (3000, 3.0), (math.inf, 3.6),
]

FL_STP_OVER5 = [
    (1000, 3.0), (1500, 3.2), (1800, 3.5),
    (2300, 4.8), (3000, 5.0), (math.inf, 5.7),
]

# Ставки для юридических лиц (упрощённая модель)
# Для категорий 3–5 и 5–7 лет хранится процент и минимальная ставка €/см³
UL_DUTY_UNDER3 = FL_STP_UNDER3  # те же проценты и минимумы
UL_DUTY_3_5: dict[str, list[tuple[int, dict[str, float]]]] = {
    "petrol": [
        (1000, {"pct": 0.0, "min_eur_cc": 1.5}),
        (1500, {"pct": 0.0, "min_eur_cc": 1.7}),
        (1800, {"pct": 0.0, "min_eur_cc": 2.5}),
        (2300, {"pct": 0.0, "min_eur_cc": 2.7}),
        (3000, {"pct": 0.0, "min_eur_cc": 3.0}),
        (math.inf, {"pct": 0.0, "min_eur_cc": 3.6}),
    ],
    "diesel": [
        (1000, {"pct": 0.0, "min_eur_cc": 1.5}),
        (1500, {"pct": 0.0, "min_eur_cc": 1.7}),
        (1800, {"pct": 0.0, "min_eur_cc": 2.5}),
        (2300, {"pct": 0.0, "min_eur_cc": 2.7}),
        (3000, {"pct": 0.0, "min_eur_cc": 3.0}),
        (math.inf, {"pct": 0.0, "min_eur_cc": 3.6}),
    ],
}

UL_DUTY_5_7: dict[str, list[tuple[int, dict[str, float]]]] = {
    "petrol": [
        (1000, {"pct": 0.0, "min_eur_cc": 3.0}),
        (1500, {"pct": 0.0, "min_eur_cc": 3.2}),
        (1800, {"pct": 0.0, "min_eur_cc": 3.5}),
        (2300, {"pct": 0.0, "min_eur_cc": 4.8}),
        (3000, {"pct": 0.0, "min_eur_cc": 5.0}),
        (math.inf, {"pct": 0.0, "min_eur_cc": 5.7}),
    ],
    "diesel": [
        (1000, {"pct": 0.0, "min_eur_cc": 3.0}),
        (1500, {"pct": 0.0, "min_eur_cc": 3.2}),
        (1800, {"pct": 0.0, "min_eur_cc": 3.5}),
        (2300, {"pct": 0.0, "min_eur_cc": 4.8}),
        (3000, {"pct": 0.0, "min_eur_cc": 5.0}),
        (math.inf, {"pct": 0.0, "min_eur_cc": 5.7}),
    ],
}

UL_DUTY_OVER7 = [
    (1000, 3.2), (1500, 3.5), (1800, 4.8),
    (2300, 5.0), (3000, 5.7), (math.inf, 7.5),
]

EXCISE_RUB_PER_HP = {
    90: 0,
    150: 61,
    200: 583,
    300: 955,
    400: 1628,
    500: 1685,
    math.inf: 1740,
}

UTIL_COEFF_FL = {
    "under_3": 0.17,
    "over_3": 0.26,
}

UTIL_BASE_UL = 20_000  # базовая ставка для юр. лиц с 01.05.2025
UTIL_COEFF_UL = {
    "under_3": 33.37,
    "3_5": 22.25,
    "5_7": 15.75,
    "7_10": 10.96,
    "over_10": 6.73,
}

CLEARANCE_FEE_TABLE = [
    (200_000, 1067),
    (450_000, 2134),
    (1_200_000, 4269),
    (3_000_000, 11746),
    (5_000_000, 16524),
    (7_000_000, 20000),
    (math.inf, 30000),
]

# ФЛ ≤3 лет — таблица по ТАМОЖЕННОЙ СТОИМОСТИ (EUR), не по объёму!
FL_STP_UNDER3_BY_VALUE_EUR = [
    (8500,    {"pct": 0.54, "min": 2.5}),
    (16700,   {"pct": 0.48, "min": 3.5}),
    (42300,   {"pct": 0.48, "min": 5.5}),
    (84500,   {"pct": 0.48, "min": 7.5}),
    (169000,  {"pct": 0.48, "min": 15.0}),
    (math.inf,{"pct": 0.48, "min": 20.0}),
]

def pick_fl_under3_rule_by_value_eur(value_eur: float) -> dict:
    """Return duty rule for a vehicle under three years old by customs value.

    Parameters
    ----------
    value_eur : float
        Customs value of the vehicle in euros.

    Returns
    -------
    dict
        Rule containing percentage (``pct``) and minimum euro-per-cc value.

    Raises
    ------
    ValueError
        If ``value_eur`` is negative.
    """
    if value_eur < 0:
        raise ValueError("value_eur must be non-negative")
    for lim, rule in FL_STP_UNDER3_BY_VALUE_EUR:
        if value_eur <= lim:
            return rule
    return FL_STP_UNDER3_BY_VALUE_EUR[-1][1]


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _get_rate(code: Currency) -> float:
    """Получить курс валюты к рублю на сегодня."""
    code = code.upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported currency: {code}. Supported: {', '.join(SUPPORTED_CURRENCIES)}"
        )
    if code == "RUB":
        return 1.0
    today = date.today()
    try:
        # Используем файловый кэш, чтобы расчёт работал без сети
        return get_cached_rate(today, code)
    except Exception:
        # Не искажаем расчёт фиктивными курсами
        raise RuntimeError("Курс ЦБ недоступен — попробуйте позже")


def _age_category(year: int, person_type: str) -> str:
    current_year = date.today().year
    age = current_year - year
    if age < 3:
        return "under_3"
    if 3 <= age <= 5:
        return "3_5"
    if person_type == "fl":
        return "over_5"
    # для юр. лиц: детализированные возрастные категории
    if 5 < age <= 7:
        return "5_7"
    if 7 < age <= 10:
        return "7_10"
    return "over_10"


def _pick_rate(table, engine_cc: int):
    for limit, rate in table:
        if engine_cc <= limit:
            return rate
    return table[-1][1]


def _excise_hp_rate(hp: int) -> int:
    for limit, rate in EXCISE_RUB_PER_HP.items():
        if hp <= limit:
            return rate
    return 0


def _compute_duty_eur(age_cat: str, engine_cc: int, value_eur: float) -> tuple[float, str]:
    if age_cat == "under_3":
        rule = pick_fl_under3_rule_by_value_eur(value_eur)
        trace = (
            f"СТП ≤3 стоимость {value_eur:.2f} EUR → pct {rule['pct']} min {rule['min']} €/см³"
        )
        duty = max(value_eur * rule["pct"], engine_cc * rule["min"])
    elif age_cat == "3_5":
        per_cc = _pick_rate(FL_STP_3_5, engine_cc)
        trace = f"СТП 3-5 лет ставка {per_cc} €/см³"
        duty = engine_cc * per_cc
    else:
        per_cc = _pick_rate(FL_STP_OVER5, engine_cc)
        trace = f"СТП >5 лет ставка {per_cc} €/см³"
        duty = engine_cc * per_cc
    return duty, trace


# ---------------------------------------------------------------------------
# Расчёт для физических лиц
# ---------------------------------------------------------------------------

def calculate_individual(*, customs_value: float, currency: Currency, engine_cc: int,
                         production_year: int, fuel: str, hp: int | None = None) -> Dict[str, float]:
    """Возвращает расчёт СТП для физического лица."""
    trace: list[str] = []
    rate = _get_rate(currency)
    value_rub = customs_value * rate
    eur_rate = _get_rate("EUR")
    value_eur = value_rub / eur_rate
    age_cat = _age_category(production_year, "fl")

    if fuel.lower() == "электро":
        # ФЛ: электромобиль считаем по СТП как ДВС (а не 15%)
        duty_eur, duty_trace = _compute_duty_eur(age_cat, engine_cc, value_eur)
    else:
        duty_eur, duty_trace = _compute_duty_eur(age_cat, engine_cc, value_eur)
    trace.append(duty_trace)

    duty_rub = duty_eur * eur_rate

    util_coeff = UTIL_COEFF_FL["under_3" if age_cat == "under_3" else "over_3"]
    util_rub = UTIL_BASE_UL * util_coeff
    fee_rub = _pick_rate(CLEARANCE_FEE_TABLE, value_rub)
    trace.append(f"Сбор за оформление: {fee_rub} руб")
    total_rub = duty_rub + util_rub + fee_rub

    return {
        "customs_value_rub": value_rub,
        "duty_eur": duty_eur,
        "eur_rate": eur_rate,
        "duty_rub": duty_rub,
        "util_rub": util_rub,
        "clearance_fee_rub": fee_rub,
        "total_rub": total_rub,
        "age_category": age_cat,
        "currency_rate": rate,
        "trace": trace,
    }


# ---------------------------------------------------------------------------
# Расчёт для юридических лиц
# ---------------------------------------------------------------------------

def calculate_company(*, customs_value: float, currency: Currency, engine_cc: int,
                       production_year: int, fuel: str, hp: int) -> Dict[str, float]:
    trace: list[str] = []
    rate = _get_rate(currency)
    value_rub = customs_value * rate
    eur_rate = _get_rate("EUR")
    value_eur = value_rub / eur_rate
    age_cat = _age_category(production_year, "ul")

    # Пошлина
    if fuel.lower() == "электро":
        duty_eur = value_eur * 0.15
        trace.append(f"Электро: 15% от {value_eur:.2f} EUR")
    else:
        if age_cat == "under_3":
            # ЮЛ ≤3 лет: 15% адвалор (если CSV не даёт иное для конкретного кода)
            duty_eur = value_eur * 0.15
            trace.append(f"ЮЛ ≤3 лет: 15% от {value_eur:.2f} EUR")
        elif age_cat in {"3_5", "5_7"}:
            table = UL_DUTY_3_5 if age_cat == "3_5" else UL_DUTY_5_7
            fuel_key = "diesel" if "диз" in fuel.lower() else "petrol"
            rule = _pick_rate(table[fuel_key], engine_cc)
            pct = rule.get("pct", 0.0)
            min_cc = rule.get("min_eur_cc", 0.0)
            if pct > 0:
                duty_eur = max(value_eur * pct, engine_cc * min_cc)
                trace.append(
                    f"ЮЛ {age_cat} {fuel_key} pct {pct} min {min_cc} €/см³"
                )
            else:
                duty_eur = engine_cc * min_cc
                trace.append(
                    f"ЮЛ {age_cat} {fuel_key} ставка {min_cc} €/см³"
                )
        else:
            per_cc = _pick_rate(UL_DUTY_OVER7, engine_cc)
            duty_eur = engine_cc * per_cc
            trace.append(f"ЮЛ >7 лет ставка {per_cc} €/см³")
    duty_rub = duty_eur * eur_rate

    # Акциз
    if fuel.lower() == "электро":
        excise_rate = 0
        excise_rub = 0
    else:
        excise_rate = _excise_hp_rate(hp)
        excise_rub = hp * excise_rate

    # НДС
    vat_rub = (value_rub + duty_rub + excise_rub) * 0.20

    # Утильсбор
    util_coeff = UTIL_COEFF_UL.get(age_cat, UTIL_COEFF_UL["over_10"])
    util_rub = UTIL_BASE_UL * util_coeff

    # Сбор за оформление
    fee_rub = _pick_rate(CLEARANCE_FEE_TABLE, value_rub)
    trace.append(f"Сбор за оформление: {fee_rub} руб")

    total_rub = duty_rub + excise_rub + vat_rub + util_rub + fee_rub

    return {
        "customs_value_rub": value_rub,
        "duty_eur": duty_eur,
        "duty_rub": duty_rub,
        "excise_rub": excise_rub,
        "vat_rub": vat_rub,
        "util_rub": util_rub,
        "clearance_fee_rub": fee_rub,
        "total_rub": total_rub,
        "eur_rate": eur_rate,
        "currency_rate": rate,
        "age_category": age_cat,
        "trace": trace,
    }


__all__ = [
    "calculate_individual",
    "calculate_company",
]
