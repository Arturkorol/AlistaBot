import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import time

# Логирование в файл
logging.basicConfig(
    filename="bot.log", level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
_cached_rate = None
_cached_date = None

# Получение курса ЦБ РФ
def get_cbr_eur_rate(retries=3, delay=2) -> float | None:
    """Получает актуальный курс евро к рублю с сайта ЦБ РФ.
    Возвращает None при ошибке (для ручного ввода)."""
    global _cached_rate, _cached_date

    # Если есть кэш на сегодня — возвращаем его
    if _cached_rate and _cached_date == datetime.today().date():
        return _cached_rate

    url = "https://www.cbr.ru/scripts/XML_daily.asp"

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}")
            r.encoding = "windows-1251"

            tree = ET.fromstring(r.text)
            for valute in tree.findall("Valute"):
                if valute.find("CharCode").text == "EUR":
                    eur_rate = float(valute.find("Value").text.replace(",", "."))
                    _cached_rate = eur_rate
                    _cached_date = datetime.today().date()
                    logging.info(f"Курс евро ЦБ РФ: {eur_rate}")
                    return eur_rate

        except Exception as e:
            logging.warning(f"Попытка {attempt} не удалась: {e}")
            if attempt < retries:
                time.sleep(delay)
    logging.error("Не удалось получить курс евро после всех попыток")
    return None

# Расчёт растаможки по ТКС
def calculate_customs(
    price_eur: float,
    engine_cc: int,
    year: int,
    car_type: str,
    power_hp: float = 0,
    weight_kg: float = 0,
    eur_rate: float | None = None,
) -> dict:
    """
    price_eur — цена авто в евро
    engine_cc — объём двигателя в см³
    year — год выпуска
    car_type — "Бензин", "Дизель", "Гибрид", "Электро"
    power_hp — мощность в л.с.
    weight_kg — масса авто в кг
    eur_rate — курс евро (если None, будет попытка получить автоматически)
    """

    current_year = datetime.now().year
    age = current_year - year

    # Таблицы ставок ТКС (€ за 1 см³)
    rates_3_5 = [
        (1000, 1.5), (1500, 1.7), (1800, 2.5),
        (2300, 2.7), (3000, 3.0), (99999, 3.6)
    ]
    rates_5_plus = [
        (1000, 3.0), (1500, 3.2), (1800, 3.5),
        (2300, 4.8), (3000, 5.0), (99999, 5.7)
    ]

    duty = 0
    excise = 0
    utilization_fee = 0

    # Логика для ДВС
    if car_type.lower() in ["бензин", "дизель"]:
        if age < 3:
            duty = max(price_eur * 0.48, engine_cc * 2.5)
        elif 3 <= age <= 5:
            rate = next(rate for limit, rate in rates_3_5 if engine_cc <= limit)
            duty = engine_cc * rate
        else:
            rate = next(rate for limit, rate in rates_5_plus if engine_cc <= limit)
            duty = engine_cc * rate

        # Акциз для >3000 см³
        if engine_cc > 3000:
            excise = power_hp * 511.0 / 100  # 511 ₽ за 1 л.с., переведём в евро позже

    # Логика для гибридов (скидка на пошлину 50%)
    elif car_type.lower() == "гибрид":
        if age < 3:
            duty = max(price_eur * 0.48, engine_cc * 2.5) * 0.5
        elif 3 <= age <= 5:
            rate = next(rate for limit, rate in rates_3_5 if engine_cc <= limit) * 0.5
            duty = engine_cc * rate
        else:
            rate = next(rate for limit, rate in rates_5_plus if engine_cc <= limit) * 0.5
            duty = engine_cc * rate

    # Логика для электромобилей
    elif car_type.lower() == "электро":
        duty = 0
        excise = 0

    # Утилизационный сбор (пример)
    utilization_fee_rub = 3400 if age > 3 else 2000

    # Если курс не передан — пробуем получить автоматически
    if eur_rate is None:
        eur_rate = get_cbr_eur_rate()
    if eur_rate is None:
        eur_rate = 100.0  # по умолчанию, будет заменён вручную

    utilization_fee = utilization_fee_rub / eur_rate
    excise = excise / eur_rate  # переводим акциз в евро

    # НДС (20%)
    vat = (price_eur + duty + excise + utilization_fee) * 0.20

    # Сбор за оформление (фикс)
    fee = 5

    total_eur = duty + excise + vat + utilization_fee + fee
    total_rub = total_eur * eur_rate

    return {
        "price_eur": round(price_eur, 2),
        "engine": engine_cc,
        "power_hp": power_hp,
        "year": year,
        "age": age,
        "eur_rate": round(eur_rate, 2),
        "duty_eur": round(duty, 2),
        "excise_eur": round(excise, 2),
        "vat_eur": round(vat, 2),
        "util_eur": round(utilization_fee, 2),
        "fee_eur": fee,
        "total_eur": round(total_eur, 2),
        "total_rub": round(total_rub, 2)
    }

