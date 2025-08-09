from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import main_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я бот по таможенной очистке авто 🚗\nВыберите действие:",
        reply_markup=main_menu(),
    )

