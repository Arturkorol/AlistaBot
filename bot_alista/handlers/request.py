from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from bot_alista.states import RequestStates
from bot_alista.keyboards.navigation import back_menu
from bot_alista.services.email import send_email_async
from bot_alista.services.pdf_report import generate_request_pdf
from bot_alista.utils.reset import reset_to_menu
from bot_alista.settings import settings

from bot_alista.constants import (
    BTN_LEAD,
    BTN_MAIN_MENU,
    BTN_FAQ,
    PROMPT_REQ_NAME,
    PROMPT_REQ_CAR,
    PROMPT_REQ_CONTACT,
    PROMPT_REQ_PRICE,
    ERROR_REQ_PRICE,
    PROMPT_REQ_COMMENT,
)
from bot_alista.handlers.faq import show_faq
from bot_alista.utils.navigation import NavigationManager, NavStep

import os
import uuid

router = Router()

# 1️⃣ Старт заявки
@router.message(F.text == BTN_LEAD)
async def start_request(message: types.Message, state: FSMContext):
    nav = NavigationManager(total_steps=5)
    await state.update_data(_nav=nav)

    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=BTN_MAIN_MENU)]],
        resize_keyboard=True,
    )

    await nav.push(
        message,
        state,
        NavStep(RequestStates.request_name, PROMPT_REQ_NAME, kb),
    )

# 2️⃣ ФИО
@router.message(RequestStates.request_name)
async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(name=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(RequestStates.request_car, PROMPT_REQ_CAR, back_menu()),
    )

# 3️⃣ Марка и модель
@router.message(RequestStates.request_car)
async def get_car(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(car=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(RequestStates.request_contact, PROMPT_REQ_CONTACT, back_menu()),
    )

# 4️⃣ Контакты
@router.message(RequestStates.request_contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(contact=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(RequestStates.request_price, PROMPT_REQ_PRICE, back_menu()),
    )

# 5️⃣ Стоимость
@router.message(RequestStates.request_price)
async def get_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return
    if nav and await nav.handle_nav(message, state):
        return
    try:
        price = float(message.text.replace(",", "."))
    except Exception:
        return await message.answer(ERROR_REQ_PRICE)
    await state.update_data(price=price)
    await nav.push(
        message,
        state,
        NavStep(RequestStates.request_comment, PROMPT_REQ_COMMENT, back_menu()),
    )

# 6️⃣ Комментарий и отправка заявки
@router.message(RequestStates.request_comment)
async def get_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return
    if nav and await nav.handle_nav(message, state):
        return
    comment = message.text.strip()
    if comment.lower() == "нет":
        comment = ""
    await state.update_data(comment=comment)

    # Получаем все данные
    data = await state.get_data()
    email_body = (
        f"📄 НОВАЯ ЗАЯВКА НА РАСТАМОЖКУ\n\n"
        f"👤 ФИО: {data['name']}\n"
        f"🚗 Авто: {data['car']}\n"
        f"📞 Контакты: {data['contact']}\n"
        f"💰 Стоимость авто: {data['price']} €\n"
        f"📝 Комментарий: {data['comment']}\n"
    )

    # Создаём PDF для прикрепления
    pdf_path = f"customs_request_{uuid.uuid4().hex}.pdf"
    generate_request_pdf(data, pdf_path)

    # Отправляем на e-mail менеджера
    email_sent = await send_email_async(
        settings.EMAIL_TO,
        "Заявка на растаможку",
        email_body,
        pdf_path,
    )
    if email_sent:
        await message.answer(
            "✅ Заявка отправлена! Наш специалист свяжется с вами.",
            reply_markup=back_menu(),
        )
    else:
        await message.answer(
            "❌ Не удалось отправить заявку. Попробуйте позже.",
            reply_markup=back_menu(),
        )
        
    #Чистим PDF
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    await reset_to_menu(message, state)
