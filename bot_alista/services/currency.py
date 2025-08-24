from __future__ import annotations

"""Utility helpers for currency conversion.

The project historically converted all prices directly to euro.  The new
implementation converts values to roubles first (using rates from the
Central Bank of Russia) and derives euro amounts from those figures.  A
legacy :func:`to_eur` helper is retained for backwards compatibility.
"""

try:
    from currency_converter_free import CurrencyConverter
except Exception:  # pragma: no cover - fallback name
    from currency_converter_free import CurrencyConverter

_converter: CurrencyConverter | None = None
_FALLBACK_RUB_RATES = {"USD": 90.0, "KRW": 0.07, "EUR": 100.0}


def _get_converter() -> CurrencyConverter:
    global _converter
    if _converter is None:
        _converter = CurrencyConverter(source="CBR")
    return _converter


def to_rub(amount: float, currency: str) -> float:
    """Convert ``amount`` from ``currency`` to Russian roubles.

    The converter uses official CBR rates when available and falls back to a
    small built‑in table if the data source is inaccessible.
    """

    code = currency.upper()
    if code == "RUB":
        return float(amount)
    try:
        converter = _get_converter()
        return float(converter.convert(amount, code, "RUB"))
    except Exception:
        rate = _FALLBACK_RUB_RATES.get(code)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate


def to_eur(amount: float, currency: str) -> float:
    """Convert ``amount`` from ``currency`` to euro.

    This helper is kept for existing callers.  Internally it converts the
    value to roubles first and then divides by the current rouble/euro rate.

    :param amount: value in the original currency
    :param currency: ISO currency code, e.g. ``"USD"``
    :return: amount converted to euros
    :raises ValueError: if currency is unsupported
    """

    code = currency.upper()
    if code == "EUR":
        return float(amount)
    amount_rub = to_rub(amount, code)
    eur_rate = to_rub(1.0, "EUR")
    return amount_rub / eur_rate
