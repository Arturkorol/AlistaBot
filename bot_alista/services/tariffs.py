from __future__ import annotations

"""Unified tariff retrieval service.

This module fetches tariff data from the Russian customs service with a
local YAML fallback.  Results are cached per process and refreshed once a
day to avoid repeated network requests."""

from datetime import date
from pathlib import Path
from typing import Any, Dict
import asyncio
import logging
import os
import xml.etree.ElementTree as ET

import aiohttp
import yaml

TARIFF_URL = "https://api.customs.gov.ru/v1/tariffs"  # Official endpoint

_cache: Dict[str, Any] | None = None
_cache_date: date | None = None


def _load_local(path: str | Path | None = None) -> Dict[str, Any]:
    """Load tariffs from the bundled ``config.yaml`` file."""
    if path is None:
        path = (
            Path(__file__).resolve().parents[2]
            / "external"
            / "tks_api_official"
            / "config.yaml"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _validate(data: Dict[str, Any]) -> None:
    required = {"clearance_tax_ranges", "vehicle_types"}
    if not isinstance(data, dict):
        raise ValueError("Tariff data must be a mapping")
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing keys: {', '.join(sorted(missing))}")


async def get_tariffs_async(path: str | Path | None = None) -> Dict[str, Any]:
    """Return tariff configuration asynchronously with caching and network fallback."""
    global _cache, _cache_date
    today = date.today()
    if _cache is not None and _cache_date == today:
        return _cache

    env_data = os.environ.get("CUSTOMS_TARIFF_DATA")
    if env_data:
        data = yaml.safe_load(env_data)
        _validate(data)
        _cache = data
        _cache_date = today
        return _cache

    data = None
    for attempt in range(3):
        try:
            timeout_cfg = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                async with session.get(TARIFF_URL) as resp:
                    resp.raise_for_status()
                    if "json" in resp.headers.get("Content-Type", ""):
                        candidate = await resp.json()
                    else:
                        text = await resp.text()
                        ET.fromstring(text)
                        candidate = _load_local(path)
            _validate(candidate)
            data = candidate
            break
        except Exception as exc:  # pragma: no cover - network failures
            logging.warning("Failed to fetch tariffs (attempt %s): %s", attempt + 1, exc)
            await asyncio.sleep(1)

    if data is None:
        logging.warning("Using local tariff config")
        data = _load_local(path)

    try:
        _validate(data)
    except ValueError:
        logging.warning("Local tariff config invalid; returning empty dict")
        data = {}

    _cache = data
    _cache_date = today
    return data


def get_tariffs(path: str | Path | None = None) -> Dict[str, Any]:
    """Synchronous wrapper around :func:`get_tariffs_async`."""
    return asyncio.run(get_tariffs_async(path))


__all__ = ["get_tariffs", "get_tariffs_async"]
