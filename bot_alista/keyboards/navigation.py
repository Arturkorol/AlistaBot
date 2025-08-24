from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.constants import (
    BTN_BACK,
    BTN_MAIN_MENU,
    BTN_FAQ,
    BTN_AGE_OVER3_YES,
    BTN_AGE_OVER3_NO,
)


def back_menu():
    kb = [
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)],
        [KeyboardButton(text=BTN_FAQ)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def yes_no_menu() -> ReplyKeyboardMarkup:
    """Keyboard with Yes/No options and main menu button."""
    kb = [
        [KeyboardButton(text=BTN_AGE_OVER3_YES), KeyboardButton(text=BTN_AGE_OVER3_NO)],
        [KeyboardButton(text=BTN_MAIN_MENU)]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
