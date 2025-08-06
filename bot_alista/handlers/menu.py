from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import main_menu
from utils.reset import reset_to_menu

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)
    await message.answer(
        "Привет! Я бот по растаможке авто 🚗\nВыберите действие:",
        reply_markup=main_menu()
    )