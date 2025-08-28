from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.constants import (
    BTN_CALC,
    BTN_LEAD,
    BTN_EXIT,
    BTN_FAQ,
)


def main_menu():
    kb = [
        [KeyboardButton(text=BTN_CALC)],
        [KeyboardButton(text=BTN_LEAD)],
        [KeyboardButton(text=BTN_FAQ)],
        [KeyboardButton(text=BTN_EXIT)],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

