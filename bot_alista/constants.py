"""Shared constants and type aliases for the Alista bot."""

from typing import Literal, Tuple

# Button labels
BTN_CALC = "\U0001F4CA Рассчитать"
BTN_BACK = "\u2B05\uFE0F Назад"
BTN_FAQ = "\u2139\uFE0F FAQ"
BTN_LEAD = "\U0001F4DE Заявка"
BTN_LAST = "\U0001F9FE Последний расчёт"
BTN_NEW = "\U0001F501 Новый расчёт"
BTN_SEND = "\U0001F4E9 Отправить менеджеру"

__all_buttons__ = [
    "BTN_CALC",
    "BTN_BACK",
    "BTN_FAQ",
    "BTN_LEAD",
    "BTN_LAST",
    "BTN_NEW",
    "BTN_SEND",
]

# Type aliases
PersonType = Literal["individual", "company"]
UsageType = Literal["personal", "commercial"]
FuelType = Literal["gasoline", "diesel", "hybrid", "electric"]
VehicleKind = Literal["car", "truck", "moto"]

# Validation ranges
ENGINE_CC_MIN = 800
ENGINE_CC_MAX = 8000
HP_MIN = 40
HP_MAX = 1200
AGE_MAX = 30

# Currency codes
CODES: Tuple[str, str, str, str] = ("EUR", "USD", "JPY", "CNY")

# Prompts and error messages
PROMPT_PERSON = "Тип лица?"
ERROR_PERSON = "Выберите тип лица."

PROMPT_USAGE = "Назначение?"
ERROR_USAGE = "Выберите назначение."

PROMPT_FUEL = "Тип топлива?"
ERROR_FUEL = "Выберите тип топлива."

PROMPT_VEHICLE = "Вид ТС?"
ERROR_VEHICLE = "Выберите вид ТС."

PROMPT_ENGINE_CC = "Объём двигателя (см³):"
ERROR_ENGINE_CC = (
    f"Введите число {ENGINE_CC_MIN}-{ENGINE_CC_MAX}."
)

PROMPT_HP = "Мощность (л.с.):"
ERROR_HP = f"Введите число {HP_MIN}-{HP_MAX}."

PROMPT_AGE = "Возраст авто (лет):"
ERROR_AGE = f"Не старше {AGE_MAX} лет."

__all__ = [
    * __all_buttons__,
    "PersonType",
    "UsageType",
    "FuelType",
    "VehicleKind",
    "ENGINE_CC_MIN",
    "ENGINE_CC_MAX",
    "HP_MIN",
    "HP_MAX",
    "AGE_MAX",
    "CODES",
    "PROMPT_PERSON",
    "ERROR_PERSON",
    "PROMPT_USAGE",
    "ERROR_USAGE",
    "PROMPT_FUEL",
    "ERROR_FUEL",
    "PROMPT_VEHICLE",
    "ERROR_VEHICLE",
    "PROMPT_ENGINE_CC",
    "ERROR_ENGINE_CC",
    "PROMPT_HP",
    "ERROR_HP",
    "PROMPT_AGE",
    "ERROR_AGE",
]
