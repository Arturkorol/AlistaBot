from __future__ import annotations

import os
import uuid
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile

from bot_alista.constants import BTN_CALC
from bot_alista.utils.navigation import NavigationManager, NavStep
from bot_alista.keyboards.navigation import back_menu
from bot_alista.services.calc import CustomsCalculator
from bot_alista.services.pdf_report import generate_calculation_pdf
from bot_alista.services.rates import get_rates
from bot_alista.utils.reset import reset_to_menu
from bot_alista.utils.formatting import format_result_message
from bot_alista.settings import settings

router = Router()


class CalcStates(StatesGroup):
    age = State()
    engine_type = State()
    engine_capacity = State()
    power = State()
    price = State()
    owner = State()
    currency = State()


@router.message(F.text == BTN_CALC)
async def start_calc(message: types.Message, state: FSMContext):
    nav = NavigationManager(total_steps=7)
    await state.update_data(_nav=nav)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.age, "Возраст авто? (new, 1-3, 3-5, 5-7, over_7)", back_menu()),
    )


@router.message(CalcStates.age)
async def get_age(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(age=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(CalcStates.engine_type, "Тип двигателя? (gasoline, diesel, electric, hybrid)", back_menu()),
    )


@router.message(CalcStates.engine_type)
async def get_engine(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(engine=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(CalcStates.engine_capacity, "Объём двигателя (см³)", back_menu()),
    )


@router.message(CalcStates.engine_capacity)
async def get_capacity(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    try:
        capacity = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(capacity=capacity)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.power, "Мощность двигателя (л.с.)", back_menu()),
    )


@router.message(CalcStates.power)
async def get_power(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    try:
        power = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(power=power)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.price, "Стоимость автомобиля", back_menu()),
    )


@router.message(CalcStates.price)
async def get_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректную стоимость")
        return
    await state.update_data(price=price)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.owner, "Импортёр? (individual/company)", back_menu()),
    )


@router.message(CalcStates.owner)
async def get_owner(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    await state.update_data(owner=message.text.strip())
    await nav.push(
        message,
        state,
        NavStep(CalcStates.currency, "Валюта (USD/EUR)", back_menu()),
    )


@router.message(CalcStates.currency)
async def finish_calc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if nav and await nav.handle_nav(message, state):
        return
    currency = message.text.strip().upper()
    data.update(currency=currency)

    calc = CustomsCalculator(config=settings.tariff_config)
    calc.set_vehicle_details(
        age=data["age"],
        engine_capacity=data["capacity"],
        engine_type=data["engine"],
        power=data["power"],
        price=data["price"],
        owner_type=data["owner"],
        currency=currency,
    )
    results = calc.calculate()
    rates = await get_rates(["USD", "EUR"])
    customs_value = calc.convert_to_local_currency(data["price"], currency)
    breakdown = {
        "customs_value_rub": customs_value,
        "duty_rub": results.get("Duty (RUB)", 0),
        "clearance_fee_rub": results.get("Clearance Fee (RUB)", 0),
        "excise_rub": results.get("Excise (RUB)", 0),
        "vat_rub": results.get("VAT (RUB)", 0),
        "util_rub": results.get("Util Fee (RUB)", 0),
        "total_rub": results.get("Total Pay (RUB)", 0) - results.get("Util Fee (RUB)", 0),
        "total_with_util_rub": results.get("Total Pay (RUB)", 0),
    }
    text = format_result_message(
        currency_code=currency,
        price_amount=data["price"],
        rates=rates,
        meta={},
        core={"breakdown": breakdown},
        util_fee_rub=results.get("Util Fee (RUB)", 0),
    )
    await message.answer(text)

    pdf_path = f"calc_report_{uuid.uuid4().hex}.pdf"
    generate_calculation_pdf(results, data, pdf_path)
    try:
        await message.answer_document(FSInputFile(pdf_path))
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    await reset_to_menu(message, state)
