from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from utils.reset import reset_to_menu

router = Router()

@router.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)
    await message.answer("❌ Действие отменено")
