from aiogram import Router, types, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot_alista.keyboards.main_menu import main_menu
from bot_alista.constants import BTN_CALC, BTN_LEAD, BTN_FAQ, BTN_MAIN_MENU
from bot_alista.handlers.calculate import start_calc
from bot_alista.handlers.request import start_request
from bot_alista.handlers.faq import show_faq
from bot_alista.utils.reset import reset_to_menu


router = Router()


@router.message(StateFilter(None), F.text)
async def fallback_top_level(message: types.Message, state: FSMContext) -> None:
    """Catch-all for unrecognized top-level text. Routes known labels manually.

    This ensures reply-keyboard presses still work even if strict equality
    filters fail due to platform-specific emoji/spacing quirks.
    """
    text = (message.text or "").strip()
    if text == BTN_CALC or text.startswith("\ud83d\udcca") or "Рассчитать" in text:
        return await start_calc(message, state)
    if text == BTN_LEAD:
        return await start_request(message, state)
    if text == BTN_FAQ:
        return await show_faq(message, state)
    if text == BTN_MAIN_MENU:
        return await reset_to_menu(message, state)

    await message.answer(
        "Пожалуйста, используйте кнопки ниже или /start для начала",
        reply_markup=main_menu(),
    )
