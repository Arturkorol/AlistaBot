from __future__ import annotations

from aiogram import types

from bot_alista.constants import (
    BTN_AGE_OVER3_NO,
    BTN_AGE_OVER3_YES,
    BTN_BACK,
    BTN_FAQ,
    BTN_MAIN_MENU,
    CURRENCY_CODES,
    BTN_METHOD_ETC,
    BTN_METHOD_CTP
)


def person_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [
            types.KeyboardButton(text="Физическое лицо"),
            types.KeyboardButton(text="Юридическое лицо"),
        ],
        [types.KeyboardButton(text=BTN_MAIN_MENU), types.KeyboardButton(text=BTN_FAQ)],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def usage_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text="Личное"), types.KeyboardButton(text="Коммерческое")],
        [types.KeyboardButton(text=BTN_BACK), types.KeyboardButton(text=BTN_MAIN_MENU)],
        [types.KeyboardButton(text=BTN_FAQ)],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def car_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text="Бензин"), types.KeyboardButton(text="Дизель")],
        [types.KeyboardButton(text="Гибрид"), types.KeyboardButton(text="Электро")],
        [types.KeyboardButton(text=BTN_BACK), types.KeyboardButton(text=BTN_MAIN_MENU)],
        [types.KeyboardButton(text=BTN_FAQ)],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def currency_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text=CURRENCY_CODES[0]), types.KeyboardButton(text=CURRENCY_CODES[1])],
        [types.KeyboardButton(text=CURRENCY_CODES[2]), types.KeyboardButton(text=CURRENCY_CODES[3])],
        [types.KeyboardButton(text=BTN_BACK), types.KeyboardButton(text=BTN_MAIN_MENU)],
        [types.KeyboardButton(text=BTN_FAQ)],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def age_over3_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text=BTN_AGE_OVER3_YES), types.KeyboardButton(text=BTN_AGE_OVER3_NO)],
        [types.KeyboardButton(text=BTN_BACK), types.KeyboardButton(text=BTN_MAIN_MENU)],
        [types.KeyboardButton(text=BTN_FAQ)],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def method_type_kb():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=BTN_METHOD_ETC)],
            [types.KeyboardButton(text=BTN_METHOD_CTP)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

__all__ = [
    "person_type_kb",
    "usage_type_kb",
    "car_type_kb",
    "currency_kb",
    "age_over3_kb",
    "method_type_kb",
]
