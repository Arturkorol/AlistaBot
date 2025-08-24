from __future__ import annotations

"""Unified tariff retrieval service.

This module fetches tariff data from the Russian customs service with a
local YAML fallback.  Results are cached per process and refreshed once a
day to avoid repeated network requests."""

from datetime import date
from pathlib import Path
from typing import Any, Dict
import logging
import xml.etree.ElementTree as ET

import requests
import yaml

TARIFF_URL = "https://customs.gov.ru/api/tariffs"  # Placeholder URL

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


def get_tariffs(path: str | Path | None = None) -> Dict[str, Any]:
    """Return tariff configuration with caching and network fallback."""
    global _cache, _cache_date
    today = date.today()
    if _cache is not None and _cache_date == today:
        return _cache
    try:
        resp = requests.get(TARIFF_URL, timeout=10)
        resp.raise_for_status()
        if "json" in resp.headers.get("Content-Type", ""):
            data = resp.json()
        else:
            # XML or unknown formats – attempt to parse, otherwise fall back
            ET.fromstring(resp.text)  # ensure it's valid XML
            data = _load_local(path)
    except Exception as exc:  # pragma: no cover - network failures
        logging.warning("Failed to fetch tariffs: %s", exc)
        data = _load_local(path)
    _cache = data
    _cache_date = today
    return data


__all__ = ["get_tariffs"]
