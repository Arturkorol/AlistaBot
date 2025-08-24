from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from bot_alista.constants import BTN_FAQ, BTN_CALC, BTN_LEAD
from bot_alista.keyboards.navigation import back_menu

router = Router()

FAQ_TEXT = (
    "ℹ️ <b>FAQ</b>\n"
    "- Как рассчитать пошлину? Используйте пункт \"{calc}\" в главном меню.\n"
    "- Как оставить заявку? Нажмите \"{lead}\" и заполните форму.\n"
    "- Нужна помощь? Свяжитесь с менеджером.".format(calc=BTN_CALC, lead=BTN_LEAD)
)


@router.message(F.text == BTN_FAQ)
async def show_faq(message: types.Message, state: FSMContext) -> None:
    await message.answer(FAQ_TEXT, reply_markup=back_menu())
