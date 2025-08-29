from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu


def build_menu(options: list[str], include_back: bool = True) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=o) for o in options]]
    if include_back:
        rows.extend(back_menu().keyboard)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


__all__ = ["build_menu"]

