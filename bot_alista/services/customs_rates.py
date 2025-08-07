import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

import requests

TARIFF_SOURCE_URL = "https://example.com/customs_rates.json"
REQUIRED_KEYS = {"source", "date", "rates"}

_cached_rates: Dict[str, Any] | None = None


def fetch_rates(url: str = TARIFF_SOURCE_URL) -> Dict[str, Any] | None:
    """Fetch customs tariff rates from ``url`` and validate them.

    Returns a dictionary with the tariff data if successful, otherwise ``None``.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - broad to capture network/json issues
        logging.error(f"Error fetching tariff rates: {exc}")
        return None

    if not isinstance(data, dict):
        logging.error("Tariff data must be a JSON object")
        return None

    missing = REQUIRED_KEYS - data.keys()
    if missing:
        logging.error(f"Tariff data missing required keys: {missing}")
        return None

    # Validate date format
    try:
        datetime.fromisoformat(str(data["date"]))
    except ValueError:
        logging.error("Invalid date format in tariff data")
        return None

    rates = data.get("rates")
    if not isinstance(rates, dict) or not rates:
        logging.error("'rates' must be a non-empty dict")
        return None

    for key, value in rates.items():
        if not isinstance(value, (int, float)):
            logging.error(f"Rate for {key} is not numeric: {value}")
            return None
        if value < 0 or value > 1_000_000:
            logging.error(f"Rate for {key} out of bounds: {value}")
            return None

    global _cached_rates
    _cached_rates = data
    return data


def get_cached_rates() -> Dict[str, Any] | None:
    """Return the most recently fetched and validated tariff data."""
    return _cached_rates


async def schedule_daily_rate_fetch(url: str = TARIFF_SOURCE_URL) -> None:
    """Fetch tariff rates once per day and log success or failure."""
    while True:
        data = fetch_rates(url)
        if data:
            logging.info(
                f"Fetched tariff rates from {data['source']} dated {data['date']}"
            )
        else:
            logging.warning("Failed to update tariff rates")
        await asyncio.sleep(24 * 60 * 60)
