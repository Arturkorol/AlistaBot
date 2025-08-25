"""Валютные курсы ЦБ РФ с кэшированием.

Использует ежедневный XML‑файл ЦБ РФ и кэширует результаты на диске
в формате JSON. Поддерживаются курсы EUR, USD, JPY и CNY.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Literal
import asyncio
import json
import xml.etree.ElementTree as ET

import aiohttp

SUPPORTED_CODES: tuple[str, ...] = ("EUR", "USD", "JPY", "CNY")
CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


_session: aiohttp.ClientSession | None = None


async def init_rates_session() -> aiohttp.ClientSession:
    """Initialize and return a shared aiohttp session for rate fetches."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_rates_session() -> None:
    """Close the shared aiohttp session used for rate fetches."""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _cache_file(for_date: date) -> Path:
    """Возвращает путь к файлу кэша для указанной даты."""
    base = Path(__file__).resolve().parents[1] / "data" / "cache"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{for_date.isoformat()}.json"


async def _fetch_cbr_rates(
    for_date: date,
    codes: Iterable[str] = SUPPORTED_CODES,
    retries: int = 3,
    timeout: float = 5.0,
) -> Dict[str, float]:
    """Запрашивает курсы валют в ЦБ РФ.

    :param for_date: дата, на которую требуется курс
    :param codes: набор кодов ISO валют
    :param retries: количество попыток при сетевых ошибках
    :param timeout: таймаут запроса в секундах
    :return: словарь ``{code: rate}``
    :raises RuntimeError: при невозможности получить данные
    """
    params = {"date_req": for_date.strftime("%d/%m/%Y")}

    for attempt in range(1, retries + 1):
        try:
            session = await init_rates_session()
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
                except ValueError as exc:  # некорректные данные в XML
                    raise RuntimeError("Ошибка разбора данных ЦБ РФ") from exc
        missing = set(codes) - rates.keys()
        if missing:
            raise RuntimeError(
                "Отсутствуют курсы валют: " + ", ".join(sorted(missing))
            )
        return rates
    raise RuntimeError("Не удалось получить курсы валют ЦБ РФ")



# ---------------------------------------------------------------------------
# Публичное API
# ---------------------------------------------------------------------------

async def get_cbr_rate(
    for_date: date,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    retries: int = 3,
    timeout: float = 5.0,
) -> float:
    """Возвращает курс указанной валюты по данным ЦБ РФ.

    :param for_date: дата, на которую требуется курс
    :param code: код ISO валюты
    :param retries: количество попыток при сетевых ошибках
    :param timeout: таймаут запроса в секундах
    :return: курс в рублях за единицу валюты
    """
    rates = await _fetch_cbr_rates(for_date, [code], retries=retries, timeout=timeout)
    return rates[code]


async def get_cached_rates(
    for_date: date,
    codes: Iterable[str] = SUPPORTED_CODES,
    retries: int = 3,
    timeout: float = 5.0,
) -> Dict[str, float]:
    """Возвращает курсы валют, используя файловый кэш.

    Если данные на указанную дату отсутствуют, выполняется запрос к ЦБ РФ
    с последующим сохранением в кэш.
    """
    cache = _cache_file(for_date)
    cached_rates: Dict[str, float] = {}
    if cache.exists():
        try:
            content = await asyncio.to_thread(cache.read_text, encoding='utf-8')
            data = json.loads(content)
            cached_rates = data.get('rates', {})
            if all(code in cached_rates for code in codes):
                return {code: cached_rates[code] for code in codes}
        except (json.JSONDecodeError, OSError):
            cached_rates = {}

    missing = [code for code in codes if code not in cached_rates]
    if missing:
        fresh = await _fetch_cbr_rates(
            for_date, missing, retries=retries, timeout=timeout
        )
        cached_rates.update(fresh)
        payload = {
            'date': for_date.isoformat(),
            'provider': 'CBR',
            'base': 'RUB',
            'rates': cached_rates,
        }
        await asyncio.to_thread(

            cache.write_text,
            json.dumps(payload, ensure_ascii=False),
            encoding='utf-8',
        )
    return {code: cached_rates[code] for code in codes}

async def get_cached_rate(
    for_date: date,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    retries: int = 3,
    timeout: float = 5.0,
) -> float:
    """Возвращает курс валюты из кэша или с запросом в ЦБ РФ."""
    rates = await get_cached_rates(for_date, [code], retries=retries, timeout=timeout)
    return rates[code]


async def currency_to_rub(
    amount: float,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    for_date: date | None = None,
) -> float:
    """Конвертирует указанное количество валюты в рубли.

    :param amount: сумма в иностранной валюте
    :param code: код валюты
    :param for_date: дата курса (по умолчанию сегодня)
    :return: сумма в рублях
    """
    if for_date is None:
        for_date = date.today()
    rate = await get_cached_rate(for_date, code)
    return amount * rate


def validate_or_prompt_rate(user_input: str) -> float:
    """Проверяет корректность введённого курса валюты.

    Допускается положительное число с не более чем четырьмя знаками после
    десятичной точки. В качестве разделителя может быть использована запятая.

    :param user_input: строка, введённая пользователем
    :return: значение курса в виде float
    :raises ValueError: при некорректном вводе
    """
    cleaned = user_input.strip().replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ValueError("Некорректное число") from exc
    if value <= 0:
        raise ValueError("Курс должен быть положительным")
    parts = cleaned.split(".")
    if len(parts) == 2 and len(parts[1]) > 4:
        raise ValueError("Не более четырёх знаков после запятой")
    return value


if __name__ == "__main__":
    async def main() -> None:
        today = date.today()
        rates = await get_cached_rates(today)
        print(f"Курсы ЦБ РФ на {today}:")
        for code, rate in rates.items():
            print(f"  {code}: {rate:.4f} руб.")
        amount = 100
        rub = await currency_to_rub(amount, "USD", today)
        print(f"{amount} USD = {rub:.2f} RUB")

    asyncio.run(main())
