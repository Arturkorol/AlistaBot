from __future__ import annotations

from typing import Dict, Any, Union
from decimal import Decimal

Number = Union[float, Decimal]


def _fmt_money_rub(v: Number) -> str:
    """Format number with space separators and append RUB sign."""
    s = f"{float(v):,.2f}"
    s = s.replace(",", " ")
    return f"{s} \u20bd"  # ₽


def _fmt_money_with_code(v: Number, code: str) -> str:
    s = f"{float(v):,.2f}"
    s = s.replace(",", " ")
    return f"{s} {code}"


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
    """Build a concise, friendly Russian message with emojis."""
    br = core["breakdown"]
    total_no_util = br["total_rub"]
    util_fee_rub = br.get("util_rub", util_fee_rub)
    total_with_util = br.get("total_with_util_rub", total_no_util + util_fee_rub)

    usd_rate = rates.get("USD")
    eur_rate = rates.get("EUR")

    lines: list[str] = []
    lines.append("\U0001F4CA \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0440\u0430\u0441\u0447\u0451\u0442\u0430:\n")

    lines.append(
        f"\U0001F4B0 \u0426\u0435\u043d\u0430 \u0430\u0432\u0442\u043e: {_fmt_money_with_code(price_amount, currency_code)}"
    )
    if usd_rate is not None:
        lines.append(f"\U0001F4C8 \u041a\u0443\u0440\u0441 USD: {_fmt_money_rub(usd_rate)}")
    if eur_rate is not None:
        lines.append(f"\U0001F4C8 \u041a\u0443\u0440\u0441 EUR: {_fmt_money_rub(eur_rate)}")
    if country_origin:
        lines.append(f"\U0001F310 \u0421\u0442\u0440\u0430\u043d\u0430 \u043f\u0440\u043e\u0438\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u044f: {country_origin}")

    lines.append(
        f"\U0001F4B3 \u0422\u0430\u043c\u043e\u0436\u0435\u043d\u043d\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c: {_fmt_money_rub(br['customs_value_rub'])}\n"
    )

    lines.append(f"\U0001F4C4 \u041f\u043e\u0448\u043b\u0438\u043d\u0430: {_fmt_money_rub(br.get('duty_rub', 0.0))}")
    if "clearance_fee_rub" in br:
        lines.append(f"\U0001F5C3\ufe0f \u041e\u0444\u043e\u0440\u043c\u043b\u0435\u043d\u0438\u0435: {_fmt_money_rub(br.get('clearance_fee_rub', 0.0))}")
    lines.append(f"\U0001F4C3 \u041d\u0414\u0421: {_fmt_money_rub(br.get('vat_rub', 0.0))}")
    lines.append(f"\U0001F4C3 \u0410\u043a\u0446\u0438\u0437: {_fmt_money_rub(br.get('excise_rub', 0.0))}\n")

    lines.append(f"\u2796 \u0418\u0442\u043e\u0433\u043e (\u0431\u0435\u0437 \u0443\u0442\u0438\u043b\u044c\u0441\u0431\u043e\u0440\u0430): {_fmt_money_rub(total_no_util)}")
    lines.append(f"\u267b\ufe0f \u0423\u0442\u0438\u043b\u044c\u0441\u0431\u043e\u0440: {_fmt_money_rub(util_fee_rub)}")
    lines.append(f"\u2705 \u0418\u0442\u043e\u0433\u043e \u043a \u043e\u043f\u043b\u0430\u0442\u0435: {_fmt_money_rub(total_with_util)}\n")

    return "\n".join(lines)

