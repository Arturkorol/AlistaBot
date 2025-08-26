from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.constants import (
    BTN_BACK,
    BTN_FAQ,
    BTN_MAIN_MENU,
    CURRENCY_CODES,
    BTN_AGE_OVER3_YES,
    BTN_AGE_OVER3_NO,
    BTN_METHOD_ETC,
    BTN_METHOD_CTP,
    BTN_METHOD_AUTO,
)


def person_type_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Физическое лицо"), KeyboardButton(text="Юридическое лицо")],
        [KeyboardButton(text=BTN_MAIN_MENU), KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def usage_type_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Личное"), KeyboardButton(text="Коммерческое")],
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        [KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def car_type_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Бензин"), KeyboardButton(text="Дизель")],
        [KeyboardButton(text="Гибрид"), KeyboardButton(text="Электро")],
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        [KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def currency_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=CURRENCY_CODES[0]), KeyboardButton(text=CURRENCY_CODES[1])],
        [KeyboardButton(text=CURRENCY_CODES[2]), KeyboardButton(text=CURRENCY_CODES[3])],
        [KeyboardButton(text=CURRENCY_CODES[4]), KeyboardButton(text=CURRENCY_CODES[5])],
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        [KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def age_over3_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=BTN_AGE_OVER3_YES), KeyboardButton(text=BTN_AGE_OVER3_NO)],
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        [KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def method_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_METHOD_ETC)],
            [KeyboardButton(text=BTN_METHOD_CTP)],
            [KeyboardButton(text=BTN_METHOD_AUTO)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


__all__ = [
    "person_type_kb",
    "usage_type_kb",
    "car_type_kb",
    "currency_kb",
    "age_over3_kb",
    "method_type_kb",
]
