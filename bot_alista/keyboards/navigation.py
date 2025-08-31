from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.constants import BTN_BACK, BTN_MAIN_MENU, BTN_FAQ


def back_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_FAQ)],
        [KeyboardButton(text=BTN_MAIN_MENU)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
