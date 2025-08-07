import uuid
import os
import asyncio

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from states import CalculationStates
from keyboards.navigation import back_menu, yes_no_menu
from services.customs import calculate_customs, get_cbr_eur_rate
from services.email import send_email
from services.pdf_report import generate_calculation_pdf
from aiogram.types import FSInputFile
from utils.reset import reset_to_menu

router = Router()


async def _check_exit(message: types.Message, state: FSMContext) -> bool:
    """Return to main menu if user pressed a navigation button."""
    if message.text in {"🏠 Главное меню", "⬅ Назад"}:
        await reset_to_menu(message, state)
        return True
    return False

# 1️⃣ Старт расчёта
@router.message(F.text == "📊 Рассчитать растаможку")
async def start_calculation(message: types.Message, state: FSMContext):
    await state.set_state(CalculationStates.calc_type)

    # Клавиатура с типами авто + главное меню
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Бензин"), types.KeyboardButton(text="Дизель")],
            [types.KeyboardButton(text="Гибрид"), types.KeyboardButton(text="Электро")],
            [types.KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите тип авто:", reply_markup=kb)

# 2️⃣ Получение типа авто
@router.message(CalculationStates.calc_type)
async def get_car_type(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    if message.text not in ["Бензин", "Дизель", "Гибрид", "Электро"]:
        return await message.answer("Пожалуйста, выберите тип авто кнопкой.")
    await state.update_data(car_type=message.text)
    await state.set_state(CalculationStates.calc_price)
    await message.answer("Введите цену авто (€):", reply_markup=back_menu())

# 3️⃣ Получение цены
@router.message(CalculationStates.calc_price)
async def get_price(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        price = float(message.text.replace(",", "."))
    except:
        return await message.answer("Введите корректную цену в евро.")
    await state.update_data(price=price)
    data = await state.get_data()
    if data["car_type"] != "Электро":
        await state.set_state(CalculationStates.calc_engine)
        await message.answer("Введите объём двигателя (см³):", reply_markup=back_menu())
    else:
        await state.set_state(CalculationStates.calc_power)
        await message.answer("Введите мощность двигателя (л.с. или кВт):", reply_markup=back_menu())

# 4️⃣ Получение объёма двигателя
@router.message(CalculationStates.calc_engine)
async def get_engine(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        engine = int(message.text)
    except:
        return await message.answer("Введите корректный объём двигателя в см³.")
    await state.update_data(engine=engine)
    await state.set_state(CalculationStates.calc_power)
    await message.answer("Введите мощность двигателя (л.с. или кВт):", reply_markup=back_menu())

# 5️⃣ Получение мощности
@router.message(CalculationStates.calc_power)
async def get_power(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        val = message.text.lower().replace(",", ".")
        if "квт" in val or "kw" in val:
            power_kw = float(''.join(c for c in val if c.isdigit() or c == "."))
            power_hp = power_kw * 1.35962
        else:
            power_hp = float(''.join(c for c in val if c.isdigit() or c == "."))
    except:
        return await message.answer("Введите корректную мощность (пример: 150 или 110 кВт).")
    await state.update_data(power_hp=round(power_hp, 1))
    await state.set_state(CalculationStates.calc_year)
    await message.answer("Введите год выпуска авто:", reply_markup=back_menu())

# 6️⃣ Получение года выпуска
@router.message(CalculationStates.calc_year)
async def get_year(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        year = int(message.text)
        if year < 1980 or year > 2100:
            raise ValueError
    except:
        return await message.answer("Введите корректный год выпуска.")
    await state.update_data(year=year)
    await state.set_state(CalculationStates.calc_weight)
    await message.answer("Введите массу авто (кг):", reply_markup=back_menu())

# 7️⃣ Масса авто → пробуем курс ЦБ РФ
@router.message(CalculationStates.calc_weight)
async def get_weight(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        weight = int(message.text)
    except:
        return await message.answer("Введите корректную массу в кг.")
    await state.update_data(weight=weight)

    eur_rate = get_cbr_eur_rate()
    if eur_rate is None:
        await message.answer(
            "❌ Не удалось получить курс евро ЦБ РФ.\n"
            "📥 Введите курс евро вручную (₽ за €):",
            reply_markup=back_menu()
        )
        return await state.set_state(CalculationStates.manual_eur_rate)

    await state.update_data(eur_rate=eur_rate)
    await run_calculation(state, message)

# 8️⃣ Ручной ввод курса
@router.message(CalculationStates.manual_eur_rate)
async def manual_rate(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    try:
        eur_rate = float(message.text.replace(",", "."))
    except:
        return await message.answer("Введите корректный курс в формате: 97.25")
    await state.update_data(eur_rate=eur_rate)
    await run_calculation(state, message)

# 9️⃣ Расчёт и вывод результата
async def run_calculation(state: FSMContext, message: types.Message):
    data = await state.get_data()
    engine = data.get("engine", 0)
    eur_rate = data.get("eur_rate")

    result = calculate_customs(
        price_eur=data["price"],
        engine_cc=engine,
        year=data["year"],
        car_type=data["car_type"],
        power_hp=data["power_hp"],
        weight_kg=data["weight"],
        eur_rate=eur_rate,
    )

    # Сохраняем результат в состояние, чтобы использовать его при отправке PDF
    await state.update_data(result=result)

    text = (
        f"💰 РАСЧЁТ ({data['car_type']})\n\n"
        f"Цена авто: {result['price_eur']} €\n"
        f"Курс: {result['eur_rate']} ₽\n"
        f"Пошлина: {result['duty_eur']} €\n"
        f"Акциз: {result['excise_eur']} €\n"
        f"НДС: {result['vat_eur']} €\n"
        f"Утильсбор: {result['util_eur']} €\n"
        f"Сбор: {result['fee_eur']} €\n\n"
        f"ИТОГО: {result['total_eur']} € ({result['total_rub']} ₽)"
    )

    await message.answer(text)
    await message.answer(
        "📧 Хотите получить PDF‑отчёт на e‑mail?",
        reply_markup=yes_no_menu(),
    )
    await state.set_state(CalculationStates.email_confirm)


# 🔟 Подтверждаем отправку PDF
@router.message(CalculationStates.email_confirm)
async def confirm_pdf(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    if message.text == "Да":
        await message.answer(
            "Введите ваш e‑mail для получения PDF‑отчёта:",
            reply_markup=back_menu(),
        )
        await state.set_state(CalculationStates.email_request)
    elif message.text == "Нет":
        await message.answer("Отчёт не будет отправлен.")
        await reset_to_menu(message, state)
    else:
        await message.answer(
            "Пожалуйста, выберите ответ: 'Да' или 'Нет'.",
            reply_markup=yes_no_menu(),
        )


# 1️⃣1️⃣ Получаем email и отправляем PDF
@router.message(CalculationStates.email_request)
async def send_pdf_report_to_user(message: types.Message, state: FSMContext):
    if await _check_exit(message, state):
        return
    user_email = message.text.strip()

    # Минимальная проверка email
    if "@" not in user_email or "." not in user_email:
        return await message.answer(
            "❌ Пожалуйста, введите корректный email.", reply_markup=back_menu()
        )

    data = await state.get_data()
    result = data.get("result")

    # Генерация PDF
    pdf_path = f"customs_report_{uuid.uuid4().hex}.pdf"
    generate_calculation_pdf(result, data, pdf_path)

    # Отправляем PDF пользователю в чат
    await message.answer_document(
        FSInputFile(pdf_path), caption="📄 Ваш расчёт в формате PDF"
    )

    # Отправка PDF на почту в отдельном потоке
    email_sent = await asyncio.to_thread(
        send_email,
        to_email=user_email,
        subject="Ваш расчёт растаможки",
        body="Добрый день! Во вложении PDF‑отчёт с результатами расчёта.",
        attachment_path=pdf_path,
    )

    if email_sent:
        await message.answer(
            "✅ PDF‑отчёт отправлен на вашу почту!", reply_markup=back_menu()
        )
    else:
        await message.answer(
            "❌ Не удалось отправить PDF‑отчёт. Попробуйте позже.",
            reply_markup=back_menu(),
        )

    # Чистим временный файл
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    await reset_to_menu(message, state)
