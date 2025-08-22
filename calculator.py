"""Расчёт таможенных платежей для импорта автомобилей в РФ.

Модуль содержит функции для вычисления полной стоимости растаможки
для физических и юридических лиц. Таблицы тарифов заданы в виде
словарей, что упрощает их актуализацию. Все сообщения и интерфейсные
подсказки представлены на русском языке.
"""
from __future__ import annotations

from datetime import date
from typing import Dict

from bot_alista.services.rates import get_cbr_rate
from bot_alista.services.customs_calculator import CustomsCalculator

# ---------------------------------------------------------------------------
# Вспомогательные структуры и таблицы тарифов
# ---------------------------------------------------------------------------

Currency = str

SUPPORTED_CURRENCIES: tuple[Currency, ...] = ("USD", "EUR", "CNY", "JPY", "RUB")

TARIFFS = CustomsCalculator.get_tariffs()

FL_STP_UNDER3 = TARIFFS["duty"]["fl"]["under_3"]
FL_STP_3_5 = TARIFFS["duty"]["fl"]["3_5"]
FL_STP_OVER5 = TARIFFS["duty"]["fl"]["over_5"]

UL_DUTY_UNDER3 = TARIFFS["duty"]["ul"]["under_3"]
UL_DUTY_3_5 = TARIFFS["duty"]["ul"]["3_5"]
UL_DUTY_5_7 = TARIFFS["duty"]["ul"]["5_7"]
UL_DUTY_OVER7 = TARIFFS["duty"]["ul"]["over_7"]

EXCISE_RUB_PER_HP = TARIFFS["excise"]["hp"]

UTIL_COEFF_FL = TARIFFS["utilization"]["fl"]
UTIL_BASE_UL = TARIFFS["utilization"]["ul"]["base"]
UTIL_COEFF_UL = TARIFFS["utilization"]["ul"]["coeffs"]

CLEARANCE_FEE_TABLE = TARIFFS["processing_fee"]


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


async def _get_rate(code: Currency) -> float:
    """Получить курс валюты к рублю на сегодня."""
    if code == "RUB":
        return 1.0
    today = date.today()
    try:
        return await get_cbr_rate(today, code)
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
    return _pick_rate(EXCISE_RUB_PER_HP, hp)


# ---------------------------------------------------------------------------
# Расчёт для физических лиц
# ---------------------------------------------------------------------------

async def calculate_individual(
    *,
    customs_value: float,
    currency: Currency,
    engine_cc: int,
    production_year: int,
    fuel: str,
    hp: int | None = None,
) -> Dict[str, float]:
    """Возвращает расчёт СТП для физического лица."""
    rate = await _get_rate(currency)
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

    eur_rate = await _get_rate("EUR")
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

async def calculate_company(
    *,
    customs_value: float,
    currency: Currency,
    engine_cc: int,
    production_year: int,
    fuel: str,
    hp: int,
) -> Dict[str, float]:
    rate = await _get_rate(currency)
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

    eur_rate = await _get_rate("EUR")
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
    fee_rub = _pick_rate(CLEARANCE_FEE_TABLE, value_rub)

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
