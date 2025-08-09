from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    kb = [
        [KeyboardButton(text="📊 Рассчитать стоимость таможенной очистки")],
        [KeyboardButton(text="📝 Оставить заявку")],
        [KeyboardButton(text="❌ Выход")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

