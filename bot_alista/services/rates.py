"""Получение и кэширование курсов валют ЦБ РФ.

Модуль обеспечивает загрузку официальных курсов валют с сайта
Центрального банка России, их файловое кэширование и основные
вспомогательные операции.
"""

from __future__ import annotations

import json
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Literal, Sequence

import requests
import xml.etree.ElementTree as ET

SUPPORTED_CODES: tuple[str, ...] = ("EUR", "USD", "JPY", "CNY")


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _cache_file(for_date: date) -> Path:
    """Возвращает путь к файлу кэша для указанной даты."""
    base_dir = Path(__file__).resolve().parents[1]
    cache_dir = base_dir / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{for_date.isoformat()}.json"


def _fetch_cbr_rates(
    for_date: date, retries: int = 3, timeout: float = 5.0
) -> Dict[str, float]:
    """Загружает курсы валют с сайта ЦБ РФ.

    Параметры:
        for_date: дата, на которую требуется курс.
        retries: количество попыток запроса при ошибке сети.
        timeout: таймаут HTTP‑запроса в секундах.

    Возвращает:
        Словарь вида ``{"EUR": 123.45, ...}`` с курсами за 1 единицу
        иностранной валюты в рублях.

    Исключения:
        RuntimeError: при ошибке сети или некорректных данных.
    """
    url_date = for_date.strftime("%d/%m/%Y")
    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={url_date}"
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            break
        except requests.RequestException as exc:  # noqa: PERF203 - ограниченный набор попыток
            last_exc = exc
            if attempt == retries - 1:
                raise RuntimeError("Ошибка сети при получении курса ЦБ РФ") from exc
            time.sleep(0.5 * (2 ** attempt))
    else:
        raise RuntimeError("Не удалось получить данные ЦБ РФ") from last_exc

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:  # noqa: PER101
        raise RuntimeError("Ошибка разбора XML от ЦБ РФ") from exc

    rates: Dict[str, float] = {}
    for valute in root.findall("Valute"):
        code = valute.findtext("CharCode")
        if code not in SUPPORTED_CODES:
            continue
        nominal_text = valute.findtext("Nominal", "1").replace(",", ".")
        value_text = valute.findtext("Value", "0").replace(",", ".")
        try:
            nominal = Decimal(nominal_text)
            value = Decimal(value_text)
            rate = float(value / nominal)
        except (InvalidOperation, ZeroDivisionError) as exc:
            raise RuntimeError(f"Некорректные данные для {code}") from exc
        rates[code] = rate

    missing = [c for c in SUPPORTED_CODES if c not in rates]
    if missing:
        raise RuntimeError(f"Нет данных для валют: {', '.join(missing)}")

    return rates


# ---------------------------------------------------------------------------
# Публичное API
# ---------------------------------------------------------------------------

def get_cbr_rate(
    for_date: date,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    retries: int = 3,
    timeout: float = 5.0,
) -> float:
    """Возвращает официальный курс ЦБ РФ для выбранной валюты."""
    rates = _fetch_cbr_rates(for_date, retries=retries, timeout=timeout)
    return rates[code]


def get_cached_rates(
    for_date: date,
    codes: Sequence[Literal["EUR", "USD", "JPY", "CNY"]] = SUPPORTED_CODES,
    retries: int = 3,
    timeout: float = 5.0,
) -> Dict[str, float]:
    """Возвращает курсы валют, используя файловый кэш.

    При отсутствии кэша выполняет запрос к ЦБ и сохраняет результат.
    """
    cache_path = _cache_file(for_date)
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            rates = data.get("rates", {})
        except Exception as exc:  # noqa: BLE001 - преобразуем в RuntimeError
            raise RuntimeError("Ошибка чтения файла кэша") from exc
    else:
        rates = _fetch_cbr_rates(for_date, retries=retries, timeout=timeout)
        data = {
            "date": for_date.isoformat(),
            "provider": "CBR",
            "base": "RUB",
            "rates": rates,
        }
        with cache_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

    result: Dict[str, float] = {}
    for code in codes:
        if code not in rates:
            # При обновлении кэша перезапишем файл
            fresh_rates = _fetch_cbr_rates(for_date, retries=retries, timeout=timeout)
            data["rates"] = fresh_rates
            with cache_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            return {c: fresh_rates[c] for c in codes}
        result[code] = rates[code]
    return result


def get_cached_rate(
    for_date: date,
    code: Literal["EUR", "USD", "JPY", "CNY"],
    retries: int = 3,
    timeout: float = 5.0,
) -> float:
    """Возвращает курс валюты, использующий файловый кэш."""
    rates = get_cached_rates(for_date, (code,), retries=retries, timeout=timeout)
    return rates[code]


def currency_to_rub(
    amount: float, code: Literal["EUR", "USD", "JPY", "CNY"], retries: int = 3
) -> float:
    """Конвертирует указанную сумму в рубли по текущему курсу ЦБ."""
    today = date.today()
    rate = get_cached_rate(today, code, retries=retries)
    return amount * rate


def validate_or_prompt_rate(user_input: str) -> float:
    """Проверяет корректность введённого курса.

    Принимает строку и возвращает значение в виде ``float``. Значение
    должно быть положительным и содержать не более четырёх знаков после
    запятой.
    """
    text = user_input.replace(",", ".").strip()
    try:
        value = Decimal(text)
    except InvalidOperation as exc:  # noqa: PER101
        raise ValueError("Некорректное значение курса") from exc
    if value <= 0:
        raise ValueError("Курс должен быть положительным")
    if abs(value.as_tuple().exponent) > 4:
        raise ValueError("Не более четырёх знаков после запятой")
    return float(value)


if __name__ == "__main__":
    today = date.today()
    rates = get_cached_rates(today)
    for code, rate in rates.items():
        print(f"{code}: {rate:.4f} RUB")
    print("100 USD ->", currency_to_rub(100, "USD"), "RUB")
