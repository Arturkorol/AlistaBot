from __future__ import annotations

from typing import Dict, Any, Union
from decimal import Decimal

Number = Union[float, Decimal]


def _fmt_money_rub(v: Number) -> str:
    """Format RUB with thin spaces and 2 decimals."""
    s = f"{float(v):,.2f}"
    return s.replace(",", " ").replace(".00", "") + " ₽"


def _fmt_money_generic(v: Number, suffix: str) -> str:
    s = f"{float(v):,.2f}"
    s = s.replace(",", " ")
    if suffix:
        return f"{s} {suffix}"
    return s


def format_result_message(
    *,
    currency_code: str,
    price_amount: float,
    rates: Dict[str, float],
    meta: Dict[str, Any],
    core: Dict[str, Any],
    util_fee_rub: Number,
    country_origin: str | None = None,
    avg_vehicle_cost_rub: Number | None = None,
    actual_costs_rub: Number | None = None,
) -> str:
    """
    Build a user-friendly Telegram message with emojis and clear sections.

    Args:
        currency_code: "EUR"|"USD"|"JPY"|"CNY"
        price_amount: original price amount in the selected currency
        rates: mapping like {"EUR": 92.86, "USD": 79.87, ...} (RUB per 1 unit)
        meta: extra info (e.g., person/usage, engine, age bucket info, notes)
        core: result from calc_breakdown_with_mode(...)
        util_fee_rub: utilization fee in RUB (ignored if ``core`` contains it)

    Returns:
        A formatted Telegram message string.
    """
    br = core["breakdown"]
    total_no_util = br["total_rub"]
    util_fee_rub = br.get("util_rub", util_fee_rub)
    total_with_util = br.get("total_with_util_rub", total_no_util + util_fee_rub)

    usd_rate = rates.get("USD")
    eur_rate = rates.get("EUR")

    duty_rate_info = meta.get("duty_rate_info", "")
    age_info = meta.get("age_info", "")
    person_usage = meta.get("person_usage", "")
    extra_notes = meta.get("extra_notes", [])

    lines: list[str] = []
    lines.append("📦 Расчёт таможенных платежей:\n")

    lines.append(f"💵 Стоимость авто: {_fmt_money_generic(price_amount, currency_code)}")
    if usd_rate is not None:
        lines.append(f"💱 Курс USD: {_fmt_money_generic(usd_rate, '₽')}")
    if eur_rate is not None:
        lines.append(f"💱 Курс EUR: {_fmt_money_generic(eur_rate, '₽')}")
    if country_origin:
        lines.append(f"🌍 Страна происхождения: {country_origin}")
    lines.append(f"💰 Таможенная стоимость: {_fmt_money_rub(br['customs_value_rub'])}\n")

    lines.append(f"🛃 Пошлина: {_fmt_money_rub(br['duty_rub'])}")
    if "clearance_fee_rub" in br:
        lines.append(
            f"📄 Сбор за таможенное оформление: {_fmt_money_rub(br['clearance_fee_rub'])}"
        )
    lines.append(f"🚫 НДС: {_fmt_money_rub(br.get('vat_rub', 0.0))}")
    lines.append(f"🚫 Акциз: {_fmt_money_rub(br.get('excise_rub', 0.0))}\n")

    lines.append(f"📌 ИТОГ без утильсбора: {_fmt_money_rub(total_no_util)}\n")
    lines.append(f"♻️ Утилизационный сбор: {_fmt_money_rub(util_fee_rub)}")
    lines.append(f"✅ ИТОГ с утильсбором: **{_fmt_money_rub(total_with_util)}**\n")

    lines.append("──────────────")
    lines.append("ℹ️ Примечания:")
    if person_usage:
        lines.append(f"• {person_usage}")
    if age_info:
        lines.append(f"• {age_info}")
    if duty_rate_info:
        lines.append(f"• Ставка пошлины: {duty_rate_info}")
    if avg_vehicle_cost_rub is not None:
        lines.append(
            f"• Средняя стоимость (РС): {_fmt_money_rub(avg_vehicle_cost_rub)}"
        )
    if actual_costs_rub is not None:
        lines.append(
            f"• Фактические затраты (СЗ): {_fmt_money_rub(actual_costs_rub)}"
        )
    for n in extra_notes:
        lines.append(f"• {n}")

    return "\n".join(lines)
