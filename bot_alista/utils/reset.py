from aiogram.fsm.context import FSMContext
from ..keyboards.main_menu import main_menu
from aiogram import types

async def reset_to_menu(message: types.Message, state: FSMContext):
    """Сброс FSM и возврат в главное меню"""
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=main_menu())
