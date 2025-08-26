"""Fetch and cache currency rates from CBR in a tiny aiohttp client."""

from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Literal
from functools import lru_cache

import aiohttp

try:  # pragma: no cover - optional dependency check
    from currency_converter_free import CurrencyConverter
except ImportError as exc:  # pragma: no cover - explicit error
    raise RuntimeError("currency_converter_free is required") from exc

SUPPORTED_CODES: tuple[str, ...] = ("EUR", "USD", "JPY", "CNY")
CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


class RatesClient:
    """Lightweight currency rates helper with file cache."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _cache_file(self, for_date: date) -> Path:
        base = Path(__file__).resolve().parents[1] / "data" / "cache"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{for_date.isoformat()}.json"

    async def fetch(
        self,
        for_date: date,
        codes: Iterable[str] = SUPPORTED_CODES,
        *,
        retries: int = 3,
        timeout: float = 5.0,
    ) -> Dict[str, float]:
        params = {"date_req": for_date.strftime("%d/%m/%Y")}
        for attempt in range(1, retries + 1):
            try:
                session = await self._session_get()
                timeout_cfg = aiohttp.ClientTimeout(total=timeout)
                async with session.get(CBR_URL, params=params, timeout=timeout_cfg) as resp:
                    resp.raise_for_status()
                    text = await resp.text(encoding="windows-1251")
                root = ET.fromstring(text)
            except (aiohttp.ClientError, ET.ParseError) as exc:
                if attempt == retries:
                    raise RuntimeError("Ошибка получения данных ЦБ РФ") from exc
                await asyncio.sleep(attempt)
                continue
            rates: Dict[str, float] = {}
            for valute in root.findall("Valute"):
                char_code = valute.findtext("CharCode")
                if char_code in codes:
                    nominal_text = valute.findtext("Nominal") or "1"
                    value_text = valute.findtext("Value") or "0"
                    try:
                        nominal = int(nominal_text)
                        value = float(value_text.replace(",", "."))
                        rates[char_code] = value / nominal
                    except ValueError as exc:
                        raise RuntimeError("Ошибка разбора данных ЦБ РФ") from exc
            missing = set(codes) - rates.keys()
            if missing:
                raise RuntimeError(
                    "Отсутствуют курсы валют: " + ", ".join(sorted(missing))
                )
            return rates
        raise RuntimeError("Не удалось получить курсы валют ЦБ РФ")

    async def get_cached(
        self,
        for_date: date,
        codes: Iterable[str] = SUPPORTED_CODES,
        *,
        retries: int = 3,
        timeout: float = 5.0,
    ) -> Dict[str, float]:
        cache = self._cache_file(for_date)
        cached_rates: Dict[str, float] = {}
        if cache.exists():
            try:
                content = await asyncio.to_thread(cache.read_text, encoding="utf-8")
                data = json.loads(content)
                cached_rates = data.get("rates", {})
                if all(code in cached_rates for code in codes):
                    return {code: cached_rates[code] for code in codes}
            except (json.JSONDecodeError, OSError):
                cached_rates = {}
        missing = [c for c in codes if c not in cached_rates]
        if missing:
            fresh = await self.fetch(for_date, missing, retries=retries, timeout=timeout)
            cached_rates.update(fresh)
            payload = {
                "date": for_date.isoformat(),
                "provider": "CBR",
                "base": "RUB",
                "rates": cached_rates,
            }
            await asyncio.to_thread(
                cache.write_text,
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        return {code: cached_rates[code] for code in codes}


_rates_client = RatesClient()


async def get_cached_rates(
    for_date: date,
    codes: Iterable[str] = SUPPORTED_CODES,
    retries: int = 3,
    timeout: float = 5.0,
) -> Dict[str, float]:
    return await _rates_client.get_cached(for_date, codes, retries=retries, timeout=timeout)


async def get_cbr_rate(
    for_date: date,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    retries: int = 3,
    timeout: float = 5.0,
) -> float:
    rates = await _rates_client.fetch(for_date, [code], retries=retries, timeout=timeout)
    return rates[code]


async def currency_to_rub(
    amount: float,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    for_date: date | None = None,
) -> float:
    if for_date is None:
        for_date = date.today()
    rate = (await get_cached_rates(for_date, [code]))[code]
    return amount * rate


async def close_rates_session() -> None:
    await _rates_client.close()


def validate_or_prompt_rate(user_input: str) -> float:
    """Validate manually provided exchange rate."""
    cleaned = user_input.strip().replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError as exc:  # pragma: no cover - validation
        raise ValueError("Некорректное число") from exc
    if value <= 0:
        raise ValueError("Курс должен быть положительным")
    parts = cleaned.split(".")
    if len(parts) == 2 and len(parts[1]) > 4:
        raise ValueError("Не более четырёх знаков после запятой")
    return value


# ---------------------------------------------------------------------------
# Simple synchronous conversion helpers
# ---------------------------------------------------------------------------
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
    """Convert ``amount`` from ``currency`` to RUB."""

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


__all__ = [
    "RatesClient",
    "SUPPORTED_CODES",
    "get_cached_rates",
    "get_cbr_rate",
    "currency_to_rub",
    "close_rates_session",
    "validate_or_prompt_rate",
    "to_eur",
    "to_rub",
]

