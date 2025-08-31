from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot_alista.utils.reset import reset_to_menu
from bot_alista.constants import CANCEL_TEXT


router = Router()


@router.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)
    await message.answer(CANCEL_TEXT)

