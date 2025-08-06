from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def back_menu():
    kb = [
        [KeyboardButton(text="⬅ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
