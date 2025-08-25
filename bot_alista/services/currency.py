from __future__ import annotations

"""Utility helpers for currency conversion."""

from datetime import date
from functools import lru_cache

try:
    from currency_converter_free import CurrencyConverter
except ImportError as exc:  # pragma: no cover - explicit error
    raise RuntimeError("currency_converter_free is required") from exc

_converter: CurrencyConverter | None = None
_FALLBACK_RATES = {
    "USD": 0.9,
    "KRW": 0.0007,
    "RUB": 0.01,
    "JPY": 0.006,
    "CNY": 0.13,
}
_EUR_TO_RUB = 1 / _FALLBACK_RATES["RUB"]


def _get_converter() -> CurrencyConverter:
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter


@lru_cache(maxsize=128)
def _get_rate(code_from: str, code_to: str, day: date) -> float:
    converter = _get_converter()
    return float(converter.convert(1, code_from, code_to, date=day))

def to_eur(amount: float, currency: str, eur_rate: float | None = None) -> float:
    """Convert ``amount`` from ``currency`` to EUR.

    ``eur_rate`` may be provided to convert values expressed in RUB without
    contacting the external rate provider.  When omitted the function attempts
    to obtain the rate from :mod:`currency_converter_free` and finally falls
    back to the static table.

    :param amount: value in the original currency
    :param currency: ISO currency code, e.g. ``"USD"``
    :param eur_rate: optional EUR/RUB rate for deterministic RUB conversion
    :return: amount converted to euros
    :raises ValueError: if currency is unsupported
    """

    code = currency.upper()
    if code == "EUR":
        return float(amount)
    try:
        if code == "RUB" and eur_rate is not None:
            return float(amount) / eur_rate
        rate = _get_rate(code, "EUR", date.today())
        return float(amount) * rate
    except Exception:
        if code == "RUB" and eur_rate is not None:
            return float(amount) / eur_rate
        rate = _FALLBACK_RATES.get(code)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate


def to_rub(amount: float, currency: str) -> float:
    """Convert ``amount`` from ``currency`` to RUB.

    The function first tries :mod:`currency_converter_free` and falls back to
    a small static rate table when conversion data is unavailable.

    :param amount: value in the original currency
    :param currency: ISO currency code, e.g. ``"USD"``
    :return: amount converted to rubles
    :raises ValueError: if currency is unsupported
    """

    code = currency.upper()
    if code == "RUB":
        return float(amount)
    try:
        rate = _get_rate(code, "RUB", date.today())
        return float(amount) * rate
    except Exception:
        if code == "EUR":
            return float(amount) * _EUR_TO_RUB
        rate_eur = _FALLBACK_RATES.get(code)
        if rate_eur is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate_eur * _EUR_TO_RUB


__all__ = ["to_eur", "to_rub"]
