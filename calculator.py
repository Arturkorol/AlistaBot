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

from bot_alista.services.rates import get_cbr_rate
from bot_alista.tariff.clearance_fee import calc_clearance_fee_rub

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
UL_DUTY_UNDER3 = FL_STP_UNDER3  # те же проценты и минимумы
UL_DUTY_3_5 = FL_STP_3_5
UL_DUTY_5_7 = FL_STP_OVER5
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
    "under_3": 0.2,
    "3_5": 0.34,
    "5_7": 0.43,
    "over_7": 0.62,
}


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _get_rate(code: Currency) -> float:
    """Получить курс валюты к рублю на сегодня."""
    if code == "RUB":
        return 1.0
    today = date.today()
    try:
        return get_cbr_rate(today, code)
    except Exception:
        # В случае недоступности сервиса ЦБ возвращаем 1 для EUR и 100 для прочих
        return 1.0 if code == "EUR" else 100.0


def _age_category(year: int, person_type: str) -> str:
    current_year = date.today().year
    age = current_year - year
    if age < 3:
        return "under_3"
    if 3 <= age <= 5:
        return "3_5"
    if person_type == "fl":
        return "over_5"
    # для юр. лиц различаем 5–7 и старше 7
    if 5 < age <= 7:
        return "5_7"
    return "over_7"


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


# ---------------------------------------------------------------------------
# Расчёт для физических лиц
# ---------------------------------------------------------------------------

def calculate_individual(*, customs_value: float, currency: Currency, engine_cc: int,
                         production_year: int, fuel: str, hp: int | None = None) -> Dict[str, float]:
    """Возвращает расчёт СТП для физического лица."""
    rate = _get_rate(currency)
    value_rub = customs_value * rate
    age_cat = _age_category(production_year, "fl")

    if fuel.lower() == "электро":
        duty_eur = customs_value * 0.15
    else:
        if age_cat == "under_3":
            pct = _pick_rate(FL_STP_UNDER3, engine_cc)
            duty_eur = max(customs_value * pct["pct"], engine_cc * pct["min"])
        elif age_cat == "3_5":
            per_cc = _pick_rate(FL_STP_3_5, engine_cc)
            duty_eur = engine_cc * per_cc
        else:
            per_cc = _pick_rate(FL_STP_OVER5, engine_cc)
            duty_eur = engine_cc * per_cc

    eur_rate = _get_rate("EUR")
    duty_rub = duty_eur * eur_rate

    util_coeff = UTIL_COEFF_FL["under_3" if age_cat == "under_3" else "over_3"]
    util_rub = UTIL_BASE_UL * util_coeff

    total_rub = duty_rub + util_rub

    return {
        "customs_value_rub": value_rub,
        "duty_eur": duty_eur,
        "eur_rate": eur_rate,
        "duty_rub": duty_rub,
        "util_rub": util_rub,
        "total_rub": total_rub,
        "age_category": age_cat,
        "currency_rate": rate,
    }


# ---------------------------------------------------------------------------
# Расчёт для юридических лиц
# ---------------------------------------------------------------------------

def calculate_company(*, customs_value: float, currency: Currency, engine_cc: int,
                       production_year: int, fuel: str, hp: int) -> Dict[str, float]:
    rate = _get_rate(currency)
    value_rub = customs_value * rate
    age_cat = _age_category(production_year, "ul")

    # Пошлина
    if fuel.lower() == "электро":
        duty_eur = customs_value * 0.15
    else:
        if age_cat == "under_3":
            duty_rule = _pick_rate(UL_DUTY_UNDER3, engine_cc)
            duty_eur = max(customs_value * duty_rule["pct"], engine_cc * duty_rule["min"])
        elif age_cat == "3_5":
            per_cc = _pick_rate(UL_DUTY_3_5, engine_cc)
            duty_eur = engine_cc * per_cc
        elif age_cat == "5_7":
            per_cc = _pick_rate(UL_DUTY_5_7, engine_cc)
            duty_eur = engine_cc * per_cc
        else:
            per_cc = _pick_rate(UL_DUTY_OVER7, engine_cc)
            duty_eur = engine_cc * per_cc

    eur_rate = _get_rate("EUR")
    duty_rub = duty_eur * eur_rate

    # Акциз
    excise_rate = _excise_hp_rate(hp)
    excise_rub = hp * excise_rate

    # НДС
    vat_rub = (value_rub + duty_rub + excise_rub) * 0.20

    # Утильсбор
    util_coeff = UTIL_COEFF_UL[age_cat if age_cat in UTIL_COEFF_UL else "over_7"]
    util_rub = UTIL_BASE_UL * util_coeff

    # Сбор за оформление
    fee_rub = calc_clearance_fee_rub(value_rub)

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
    }


# ---------------------------------------------------------------------------
# Формирование текстовых ответов для бота
# ---------------------------------------------------------------------------


def format_individual_result(data: Dict[str, float]) -> str:
    return (
        "📦 Таможенная стоимость: " + _format_money(data["customs_value_rub"]) + " ₽\n"
        "🛃 СТП: " + _format_money(data["duty_rub"]) + " ₽\n"
        "♻️ Утильсбор: " + _format_money(data["util_rub"]) + " ₽\n"
        "✅ Итоговая сумма: " + _format_money(data["total_rub"]) + " ₽"
    )


def format_company_result(data: Dict[str, float]) -> str:
    return (
        "📦 Таможенная стоимость: " + _format_money(data["customs_value_rub"]) + " ₽\n"
        "🛃 Пошлина: " + _format_money(data["duty_rub"]) + " ₽\n"
        "🚗 Акциз: " + _format_money(data["excise_rub"]) + " ₽\n"
        "💰 НДС: " + _format_money(data["vat_rub"]) + " ₽\n"
        "♻️ Утилизационный сбор: " + _format_money(data["util_rub"]) + " ₽\n"
        "📄 Сбор за оформление: " + _format_money(data["clearance_fee_rub"]) + " ₽\n"
        "✅ Итоговая сумма: " + _format_money(data["total_rub"]) + " ₽"
    )


__all__ = [
    "calculate_individual",
    "calculate_company",
    "format_individual_result",
    "format_company_result",
]
