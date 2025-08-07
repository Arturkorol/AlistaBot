import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import time

from . import tariffs

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
    import requests

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
    *,
    eco_class: str | None = None,
    is_new: bool | None = None,
    vehicle_category: str = "M1",
) -> dict:
    """Расчёт полной стоимости растаможки.

    Дополнительные параметры:
    eco_class — экологический класс (влияет на утилизационный сбор)
    is_new — является ли автомобиль новым
    vehicle_category — категория ТС по ОКТМ
    """

    current_year = datetime.now().year
    age = current_year - year
    if is_new is None:
        is_new = age < 3

    # Пошлина
    duty = 0.0
    if car_type.lower() in ["бензин", "дизель", "гибрид"]:
        if is_new:
            duty = max(
                price_eur * tariffs.NEW_DUTY_PERCENT,
                engine_cc * tariffs.NEW_DUTY_MIN_PER_CC,
            )
        else:
            rate = tariffs.get_used_duty_rate(engine_cc, age > 5)
            if car_type.lower() == "гибрид":
                rate *= 0.5
            duty = engine_cc * rate
    elif car_type.lower() == "электро":
        duty = 0.0

    # Курс евро
    if eur_rate is None:
        eur_rate = get_cbr_eur_rate() or 100.0

    # Акциз
    excise = 0.0
    if car_type.lower() in ["бензин", "дизель"] and engine_cc > 3000:
        excise_rub = power_hp * tariffs.EXCISE_RATE_RUB_PER_HP
        excise = excise_rub / eur_rate

    # Утилизационный сбор
    util_fee_rub = tariffs.get_utilization_fee(
        vehicle_category, is_new, eco_class
    )
    utilization_fee = util_fee_rub / eur_rate

    # НДС
    vat = (price_eur + duty + excise + utilization_fee) * tariffs.VAT_RATE

    # Прочие сборы
    fee = tariffs.FEE_EUR

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
        "total_rub": round(total_rub, 2),
    }

