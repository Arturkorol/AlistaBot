from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from ..constants import BTN_CALC, BTN_LEAD, BTN_EXIT

def main_menu():
    kb = [
        [KeyboardButton(text=BTN_CALC)],
        [KeyboardButton(text=BTN_LEAD)],
        [KeyboardButton(text=BTN_EXIT)]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

