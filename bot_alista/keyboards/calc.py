from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu


def _build(options: list[str]) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=o) for o in options]]
    keyboard.extend(back_menu().keyboard)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def age_keyboard() -> ReplyKeyboardMarkup:
    return _build(["new", "1-3", "3-5", "5-7", "over_7"])


def engine_keyboard() -> ReplyKeyboardMarkup:
    return _build(["gasoline", "diesel", "electric", "hybrid"])


def owner_keyboard() -> ReplyKeyboardMarkup:
    return _build(["individual", "company"])


def currency_keyboard() -> ReplyKeyboardMarkup:
    return _build(["USD", "EUR"])


__all__ = [
    "age_keyboard",
    "engine_keyboard",
    "owner_keyboard",
    "currency_keyboard",
]

