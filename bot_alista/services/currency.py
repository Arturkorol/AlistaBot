from __future__ import annotations

"""Utility helpers for currency conversion to EUR."""

try:
    from currency_converter import CurrencyConverter
except Exception:  # pragma: no cover - fallback name
    from currency_converter_free import CurrencyConverter

_converter: CurrencyConverter | None = None
_FALLBACK_RATES = {"USD": 0.9, "KRW": 0.0007, "RUB": 0.01}


def _get_converter() -> CurrencyConverter:
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter


def to_eur(amount: float, currency: str) -> float:
    """Convert ``amount`` from ``currency`` to EUR.

    :param amount: value in the original currency
    :param currency: ISO currency code, e.g. ``"USD"``
    :return: amount converted to euros
    :raises ValueError: if currency is unsupported
    """
    code = currency.upper()
    if code == "EUR":
        return float(amount)
    try:
        converter = _get_converter()
        return float(converter.convert(amount, code, "EUR"))
    except Exception:
        rate = _FALLBACK_RATES.get(code)
        if rate is None:
            raise ValueError(f"Unsupported currency: {currency}")
        return float(amount) * rate
