"""Currency rates utilities with simple daily caching."""

from __future__ import annotations

import logging
from datetime import date
from functools import lru_cache
from typing import Dict, Iterable

import requests

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"


@lru_cache()
def _fetch_daily(_: date) -> Dict[str, Dict[str, float]]:
    """Fetch daily rates from the CBR public API.

    The returned mapping is keyed by currency code and contains ``Value`` and
    ``Nominal`` fields. ``date`` is part of the cache key but the API only
    serves the latest rates which is sufficient for this project.
    """
    resp = requests.get(CBR_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()["Valute"]
    return {code: {"Value": float(v["Value"]), "Nominal": float(v["Nominal"])} for code, v in data.items()}


def get_cached_rates(day: date, codes: Iterable[str]) -> Dict[str, float]:
    """Return RUB rates for requested currency ``codes`` on ``day``.

    Rates are expressed as RUB for one unit of foreign currency and cached per
    day. Raises an exception if fetching fails or a currency is missing.
    """
    try:
        all_rates = _fetch_daily(day)
        rates: Dict[str, float] = {}
        for code in codes:
            info = all_rates[code]
            rates[code] = round(info["Value"] / info["Nominal"], 6)
        return rates
    except Exception as exc:  # pragma: no cover - network related
        logging.exception("Failed to fetch currency rates: %s", exc)
        raise


def currency_to_rub(amount: float, currency_code: str, day: date) -> float:
    """Convert ``amount`` in ``currency_code`` to RUB for the given ``day``."""
    rates = get_cached_rates(day, codes=[currency_code])
    return round(amount * rates[currency_code], 2)
