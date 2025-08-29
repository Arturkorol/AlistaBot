from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from bot_alista.constants import BTN_FAQ, BTN_CALC, BTN_LEAD, FAQ_TEXT_TEMPLATE
from bot_alista.keyboards.navigation import back_menu


router = Router()


@router.message(F.text == BTN_FAQ)
async def show_faq(message: types.Message, state: FSMContext) -> None:
    text = FAQ_TEXT_TEMPLATE.format(calc=BTN_CALC, lead=BTN_LEAD)
    await message.answer(text, reply_markup=back_menu())

