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
from bot_alista.keyboards.calc import (
    age_keyboard,
    engine_keyboard,
    owner_keyboard,
    currency_keyboard,
)
from bot_alista.keyboards.calc import power_unit_keyboard
from bot_alista.services.calc import CustomsCalculator
from bot_alista.services.pdf_report import generate_calculation_pdf
from bot_alista.services.rates import get_rates
from bot_alista.utils.reset import reset_to_menu
from bot_alista.utils.formatting import format_result_message
from bot_alista.settings import settings
from bot_alista.utils.navigation import with_nav

router = Router()


class CalcStates(StatesGroup):
    age = State()
    engine_type = State()
    engine_capacity = State()
    power_unit = State()
    power = State()
    price = State()
    owner = State()
    currency = State()


@router.message(F.text == BTN_CALC)
async def start_calc(message: types.Message, state: FSMContext):
    nav = NavigationManager(total_steps=9)
    await state.update_data(_nav=nav)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.age, "Возраст авто?", age_keyboard()),
    )


@router.message(CalcStates.age)
@with_nav
async def get_age(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip()
    if choice not in {"new", "1-3", "3-5", "5-7", "over_7"}:
        await message.answer("Выберите возраст из предложенных вариантов", reply_markup=age_keyboard())
        return
    await state.update_data(age=choice)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.engine_type, "Тип двигателя?", engine_keyboard()),
    )


@router.message(CalcStates.engine_type)
@with_nav
async def get_engine(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip()
    if choice not in {"gasoline", "diesel", "electric", "hybrid"}:
        await message.answer("Выберите тип двигателя из предложенных", reply_markup=engine_keyboard())
        return
    await state.update_data(engine=choice)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.engine_capacity, "Объём двигателя (см³)", back_menu()),
    )


@router.message(CalcStates.engine_capacity)
@with_nav
async def get_capacity(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    try:
        capacity = int(message.text)
    except ValueError:
        await message.answer("Введите число")
        return
    await state.update_data(capacity=capacity)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.power_unit, "Select power unit", power_unit_keyboard()),
    )


@router.message(CalcStates.power_unit)
@with_nav
async def get_power_unit(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip().lower()
    if choice not in {"hp", "kw"}:
        await message.answer("Choose power unit from keyboard.", reply_markup=power_unit_keyboard())
        return
    await state.update_data(power_unit=choice)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.power, "Enter engine power", back_menu()),
    )

@router.message(CalcStates.power)
@with_nav
async def get_power(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    data = await state.get_data()
    if data.get("power_unit") not in {"hp", "kw"}:
        await nav.push(message, state, NavStep(CalcStates.power_unit, "Select power unit", power_unit_keyboard()))
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
@with_nav
async def get_price(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректную стоимость")
        return
    await state.update_data(price=price)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.owner, "Импортёр?", owner_keyboard()),
    )


@router.message(CalcStates.owner)
@with_nav
async def get_owner(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip()
    if choice not in {"individual", "company"}:
        await message.answer("Выберите импортёра из вариантов", reply_markup=owner_keyboard())
        return
    await state.update_data(owner=choice)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.currency, "Валюта?", currency_keyboard()),
    )


@router.message(CalcStates.currency)
@with_nav
async def finish_calc(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    data = await state.get_data()
    currency = message.text.strip().upper()
    if currency not in {"USD", "EUR"}:
        await message.answer("Выберите валюту из списка", reply_markup=currency_keyboard())
        return
    data.update(currency=currency)

    # Fetch a consistent FX snapshot, including the base tariff currency
    tariffs = (settings.tariff_config or {}).get("tariffs", {})
    base_cur = str(tariffs.get("currency", "EUR")).upper()
    wanted = sorted({currency, base_cur, "USD", "EUR"})
    rates = await get_rates(wanted)
    calc = CustomsCalculator(config=settings.tariff_config, rates_snapshot=rates)
    calc.set_vehicle_details(
        age=data["age"],
        engine_capacity=data["capacity"],
        engine_type=data["engine"],
        power=data["power"],
        price=data["price"],
        owner_type=data["owner"],
        currency=currency,
        power_unit=data.get("power_unit", "hp"),
    )
    try:
        results = calc.calculate()
    except Exception as e:
        await message.answer(f"Calculation error: {e}")
        await reset_to_menu(message, state)
        return
    customs_value = calc.convert_to_local_currency(data["price"], currency)
    # Enrich results for downstream formatting/PDF consumers
    results.setdefault("Price (RUB)", customs_value)
    eur_rate = rates.get("EUR")
    if eur_rate is not None:
        results["eur_rate"] = eur_rate
        if currency == "EUR":
            results["price_eur"] = data["price"]
        else:
            cur_rate = rates.get(currency)
            if cur_rate and eur_rate:
                results["price_eur"] = data["price"] * (cur_rate / eur_rate)
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
