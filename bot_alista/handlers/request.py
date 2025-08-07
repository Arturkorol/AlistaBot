from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states import RequestStates
from keyboards.navigation import back_menu
from services.email import send_email
from services.pdf_report import generate_request_pdf
from utils.reset import reset_to_menu
from config import EMAIL_TO

import os
import uuid

router = Router()

# 1️⃣ Старт заявки
@router.message(F.text == "📝 Оставить заявку")
async def start_request(message: types.Message, state: FSMContext):
    await state.set_state(RequestStates.request_name)

    # Клавиатура для первого шага — только "Главное меню"
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

    await message.answer("Введите ФИО владельца:", reply_markup=kb)

# 2️⃣ ФИО
@router.message(RequestStates.request_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(RequestStates.request_car)
    await message.answer("Введите марку и модель авто:", reply_markup=back_menu())

# 3️⃣ Марка и модель
@router.message(RequestStates.request_car)
async def get_car(message: types.Message, state: FSMContext):
    await state.update_data(car=message.text.strip())
    await state.set_state(RequestStates.request_contact)
    await message.answer("Введите контактные данные (телефон, e‑mail):", reply_markup=back_menu())

# 4️⃣ Контакты
@router.message(RequestStates.request_contact)
async def get_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text.strip())
    await state.set_state(RequestStates.request_price)
    await message.answer("Введите ориентировочную стоимость авто (€):", reply_markup=back_menu())

# 5️⃣ Стоимость
@router.message(RequestStates.request_price)
async def get_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except:
        return await message.answer("Введите корректную цену в евро.")
    await state.update_data(price=price)
    await state.set_state(RequestStates.request_comment)
    await message.answer("Введите дополнительный комментарий (или напишите 'нет'):", reply_markup=back_menu())

# 6️⃣ Комментарий и отправка заявки
@router.message(RequestStates.request_comment)
async def get_comment(message: types.Message, state: FSMContext):
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
    if send_email(EMAIL_TO, "Заявка на растаможку", email_body, pdf_path):
        await message.answer("✅ Заявка отправлена! Наш специалист свяжется с вами.", 
                             reply_markup=back_menu())
    else:
        await message.answer("❌ Не удалось отправить заявку. Попробуйте позже.", 
                             reply_markup=back_menu())
        
    #Чистим PDF
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    await reset_to_menu(message, state)
