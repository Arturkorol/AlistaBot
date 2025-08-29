from aiogram.fsm.context import FSMContext
from bot_alista.keyboards.main_menu import main_menu
from bot_alista.constants import BTN_MAIN_MENU
from aiogram import types

async def reset_to_menu(message: types.Message, state: FSMContext):
    """Сброс FSM и возврат в главное меню"""
    await state.clear()
    await message.answer(f"{BTN_MAIN_MENU}:", reply_markup=main_menu())
