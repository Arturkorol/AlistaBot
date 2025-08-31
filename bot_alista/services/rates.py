"""Fetch currency rates (RUB per 1 unit) from CBR XML_daily."""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Set
from bot_alista.models.constants import SUPPORTED_CURRENCY_CODES
import xml.etree.ElementTree as ET

from typing import TYPE_CHECKING
try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore

if TYPE_CHECKING:
    from aiohttp import ClientSession  # type: ignore

_CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
_cache: dict[str, tuple[float, float]] = {}
_session: "ClientSession | None" = None

async def _get_session():
    global _session
    if _session is None:
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for fetching CBR rates")
        _session = aiohttp.ClientSession()
    return _session


def _parse_cbr_xml(xml_bytes: bytes, wanted: Set[str]) -> Dict[str, float]:
    root = ET.fromstring(xml_bytes)
    out: Dict[str, float] = {}
    for val in root.findall("Valute"):
        code_el = val.find("CharCode")
        if code_el is None:
            continue
        code = (code_el.text or "").upper().strip()
        if wanted and code not in wanted:
            continue
        nominal_el = val.find("Nominal")
        value_el = val.find("Value")
        try:
            nominal = int((nominal_el.text or "1").strip()) if nominal_el is not None else 1
            value_str = (value_el.text or "0").replace(" ", "").replace(",", ".") if value_el is not None else "0"
            value = float(value_str)
            if nominal <= 0:
                continue
            rate = value / nominal  # RUB per 1 unit
            out[code] = rate
        except Exception:
            continue
    # CBR XML does not include RUB; define it explicitly at 1.0
    out.setdefault("RUB", 1.0)
    return out


async def get_rates(
    codes: list[str] | None = None,
    ttl: int = 3600,
    force_refresh: bool = False,
) -> dict[str, float]:
    codes = [c.upper() for c in (codes or list(SUPPORTED_CURRENCY_CODES))]
    now = time.time()
    rates: dict[str, float] = {}

    # Use cache where valid
    missing: list[str] = []
    for code in codes:
        cached = _cache.get(code)
        if not force_refresh and cached is not None and (now - cached[1] < ttl):
            rates[code] = cached[0]
        else:
            missing.append(code)

    if missing:
        sess = await _get_session()
        async with sess.get(_CBR_URL, timeout=10) as resp:
            resp.raise_for_status()
            xml_bytes = await resp.read()
        parsed = _parse_cbr_xml(xml_bytes, set(codes))
        for code in missing:
            if code in parsed:
                rate = parsed[code]
                _cache[code] = (rate, now)
                rates[code] = rate

    return rates


async def close_rates_session() -> None:
    global _session
    if _session is not None:
        try:
            await _session.close()
        finally:
            _session = None
