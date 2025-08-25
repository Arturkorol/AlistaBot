from __future__ import annotations

"""Utility helpers for currency conversion."""

from datetime import date
from typing import Dict

import requests

try:  # pragma: no cover - optional dependency
    from currency_converter_free import CurrencyConverter
except Exception:  # pragma: no cover - fallback name
    from currency_converter_free import CurrencyConverter

_converter: CurrencyConverter | None = None
_FALLBACK_RATES = {"USD": 0.9, "KRW": 0.0007, "RUB": 0.01}
_EUR_TO_RUB = 1 / _FALLBACK_RATES["RUB"]

FTS_URL = "https://customs.example/rates/{date}"
_fts_cache: Dict[str, Dict[str, float]] = {}


def _get_converter() -> CurrencyConverter:
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter


def _get_fts_rates(rate_date: date) -> Dict[str, float]:
    """Fetch daily rates from the FTS endpoint with simple caching."""

    key = rate_date.isoformat()
    if key in _fts_cache:
        return _fts_cache[key]

    resp = requests.get(FTS_URL.format(date=key), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    rates = {k.upper(): float(v) for k, v in data.items()}
    _fts_cache[key] = rates
    return rates

def to_eur(
    amount: float,
    currency: str,
    eur_rate: float | None = None,
    *,
    rate_date: date | None = None,
) -> float:
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
    if rate_date is not None:
        rates = _get_fts_rates(rate_date)
        eur = rates.get("EUR")
        src = rates.get(code)
        if eur is None or (src is None and code != "RUB"):
            raise ValueError(f"Unsupported currency: {currency}")
        if code == "RUB":
            rate = eur
            return float(amount) / rate
        return float(amount) * src / eur
    if code == "RUB" and eur_rate is not None:
        return float(amount) / eur_rate

    try:
        converter = _get_converter()
        return float(converter.convert(amount, code, "EUR"))
    except Exception:
        if code == "RUB" and eur_rate is not None:
            return float(amount) / eur_rate
        rate = _FALLBACK_RATES.get(code)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate


def to_rub(amount: float, currency: str, *, rate_date: date | None = None) -> float:
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
    if rate_date is not None:
        rates = _get_fts_rates(rate_date)
        rate = rates.get(code)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate
    try:
        converter = _get_converter()
        return float(converter.convert(amount, code, "RUB"))
    except Exception:
        if code == "EUR":
            return float(amount) * _EUR_TO_RUB
        rate_eur = _FALLBACK_RATES.get(code)
        if rate_eur is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate_eur * _EUR_TO_RUB


__all__ = ["to_eur", "to_rub"]
