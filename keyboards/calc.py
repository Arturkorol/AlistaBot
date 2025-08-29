from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu
from bot_alista.keyboards.common import build_menu


def _build(options: list[str]) -> ReplyKeyboardMarkup:
    return build_menu(options, include_back=True)


def age_keyboard() -> ReplyKeyboardMarkup:
    return _build(["new", "1-3", "3-5", "5-7", "over_7"])


def engine_keyboard() -> ReplyKeyboardMarkup:
    return _build(["gasoline", "diesel", "electric", "hybrid"])


def owner_keyboard() -> ReplyKeyboardMarkup:
    return _build(["individual", "company"])


def currency_keyboard() -> ReplyKeyboardMarkup:
    return _build(["USD", "EUR"])


def power_unit_keyboard() -> ReplyKeyboardMarkup:
    """Select power unit for engine power input."""
    return _build(["HP", "kW"])


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    # Russian labels via Unicode escapes to avoid encoding issues
    return _build(["\u0414\u0430", "\u041d\u0435\u0442"])  # Да / Нет


__all__ = [
    "age_keyboard",
    "engine_keyboard",
    "owner_keyboard",
    "currency_keyboard",
    "power_unit_keyboard",
    "yes_no_keyboard",
]
