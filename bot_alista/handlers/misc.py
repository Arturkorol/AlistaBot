from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot_alista.keyboards.main_menu import main_menu


router = Router()


@router.message(StateFilter(None))
async def fallback_top_level(message: types.Message, state: FSMContext) -> None:
    """Catch-all for any unrecognized top-level messages/commands.

    Keeps aiogram from logging "Update is not handled" for common cases
    (unknown commands, free text) and nudges the user to use the menu.
    """
    await message.answer(
        "Пожалуйста, используйте кнопки ниже или /start для начала",
        reply_markup=main_menu(),
    )

