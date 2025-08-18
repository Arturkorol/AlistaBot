"""Handlers for processing contact requests from the main menu."""

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from ..states import RequestStates
from ..keyboards.navigation import back_menu
from ..utils.reset import reset_to_menu
from ..services.email import send_email
from ..config import EMAIL_TO

router = Router()

@router.message(F.text == "📝 Оставить заявку")
async def start_request(message: types.Message, state: FSMContext) -> None:
    """Initiate the request conversation by asking for contact details."""
    await state.set_state(RequestStates.contact)
    await message.answer(
        "Пожалуйста, отправьте ваш номер телефона или контактную информацию.",
        reply_markup=back_menu(),
    )


@router.message(RequestStates.contact)
async def handle_contact(message: types.Message, state: FSMContext) -> None:
    """Receive contact info, send it via email and return to main menu."""
    if message.text in {"🏠 Главное меню", "⬅ Назад"}:
        await reset_to_menu(message, state)
        return

    contact = message.text.strip()
    body = (
        f"Заявка от {message.from_user.full_name} (@{message.from_user.username}):\n"
        f"{contact}"
    )
    success = send_email(EMAIL_TO, "Новая заявка", body)

    if success:
        await message.answer("✅ Спасибо! Мы свяжемся с вами в ближайшее время.")
    else:
        await message.answer("❌ Не удалось отправить заявку. Попробуйте позже.")

    await reset_to_menu(message, state)
