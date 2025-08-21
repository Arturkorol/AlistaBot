from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def back_menu():
    kb = [
        [KeyboardButton(text="⬅ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def yes_no_menu() -> ReplyKeyboardMarkup:
    """Keyboard with Yes/No options and main menu button."""
    kb = [
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
        [KeyboardButton(text="🏠 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
