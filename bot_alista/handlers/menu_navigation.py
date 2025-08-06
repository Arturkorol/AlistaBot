from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from utils.reset import reset_to_menu

router = Router()

@router.message(F.text == "🏠 Главное меню")
async def go_main_menu(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)

@router.message(F.text == "⬅ Назад")
async def go_back(message: types.Message, state: FSMContext):
    # Просто возвращаем в главное меню
    await reset_to_menu(message, state)
