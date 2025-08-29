from __future__ import annotations

import os
import uuid
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from bot_alista.constants import (
    BTN_CALC,
    PROMPT_YEAR,
    PROMPT_ENGINE_TYPE,
    PROMPT_ENGINE_CAPACITY,
    PROMPT_POWER_UNIT,
    PROMPT_POWER,
    PROMPT_PRICE,
    PROMPT_OWNER,
    PROMPT_CURRENCY,
    ERROR_SELECT_FROM_KEYBOARD,
    ERROR_SELECT_YES_NO,
    ERROR_ENTER_NUMBER,
    ERROR_REQ_PRICE,
    ERROR_ENTER_YEAR_NUMBER,
    ERROR_YEAR_RANGE,
    ERROR_INVALID_AGE_OR_YEAR,
    PROMPT_OLDER_THAN_3,
    PROMPT_OLDER_THAN_5,
)
from bot_alista.utils.navigation import NavigationManager, NavStep, with_nav
from bot_alista.keyboards.navigation import back_menu
from bot_alista.keyboards.calc import (
    age_keyboard,
    engine_keyboard,
    owner_keyboard,
    currency_keyboard,
    power_unit_keyboard,
    yes_no_keyboard,
)
from bot_alista.states.calc import CalcStates
from bot_alista.services.calc import CustomsCalculator
from bot_alista.services.pdf_report import generate_calculation_pdf
from bot_alista.services.rates import get_rates
from bot_alista.utils.reset import reset_to_menu
from bot_alista.utils.formatting import format_result_message
from bot_alista.settings import settings


router = Router()


@router.message(F.text == BTN_CALC)
async def start_calc(message: types.Message, state: FSMContext):
    nav = NavigationManager(total_steps=9)
    await state.update_data(_nav=nav)
    await nav.push(
        message,
        state,
        NavStep(CalcStates.year, PROMPT_YEAR, back_menu()),
    )


@router.message(CalcStates.year)
@with_nav
async def get_year(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    from datetime import datetime
    txt = message.text.strip()
    try:
        year = int(txt)
    except ValueError:
        await message.answer(ERROR_ENTER_YEAR_NUMBER)
        return
    current_year = datetime.now().year
    if year < 1950 or year > current_year:
        await message.answer(ERROR_YEAR_RANGE.format(current_year=current_year))
        return
    age_years = current_year - year
    await state.update_data(year=year)

    if age_years < 3:
        await state.update_data(age="1-3")
        await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
        return
    if age_years == 3:
        await nav.push(message, state, NavStep(CalcStates.older_than_3, PROMPT_OLDER_THAN_3, yes_no_keyboard()))
        return
    if 3 < age_years < 5:
        await state.update_data(age="3-5")
        await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
        return
    if age_years == 5:
        await nav.push(message, state, NavStep(CalcStates.older_than_5, PROMPT_OLDER_THAN_5, yes_no_keyboard()))
        return
    if 5 < age_years <= 7:
        await state.update_data(age="5-7")
    else:
        await state.update_data(age="over_7")
    await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))


@router.message(CalcStates.age)
@with_nav
async def get_age(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    # Fallback: allow user to type a year or select a bucket
    from datetime import datetime
    text = message.text.strip()
    try:
        year = int(text)
        current_year = datetime.now().year
        if 1950 <= year <= current_year:
            age_years = current_year - year
            await state.update_data(year=year)
            if age_years < 3:
                await state.update_data(age="1-3")
                await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
                return
            if age_years == 3:
                await nav.push(message, state, NavStep(CalcStates.older_than_3, PROMPT_OLDER_THAN_3, yes_no_keyboard()))
                return
            if 3 < age_years < 5:
                await state.update_data(age="3-5")
                await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
                return
            if age_years == 5:
                await nav.push(message, state, NavStep(CalcStates.older_than_5, PROMPT_OLDER_THAN_5, yes_no_keyboard()))
                return
            if 5 < age_years <= 7:
                await state.update_data(age="5-7")
            else:
                await state.update_data(age="over_7")
            await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
            return
    except ValueError:
        pass

    choice = text
    if choice not in {"new", "1-3", "3-5", "5-7", "over_7"}:
        await message.answer(ERROR_INVALID_AGE_OR_YEAR, reply_markup=age_keyboard())
        return
    await state.update_data(age=choice)
    await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))


@router.message(CalcStates.engine_type)
@with_nav
async def get_engine(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip()
    if choice not in {"gasoline", "diesel", "electric", "hybrid"}:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=engine_keyboard())
        return
    await state.update_data(engine=choice)
    await nav.push(message, state, NavStep(CalcStates.engine_capacity, PROMPT_ENGINE_CAPACITY, back_menu()))


@router.message(CalcStates.engine_capacity)
@with_nav
async def get_capacity(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    try:
        capacity = int(message.text)
    except ValueError:
        await message.answer(ERROR_ENTER_NUMBER)
        return
    await state.update_data(capacity=capacity)
    await nav.push(message, state, NavStep(CalcStates.power_unit, PROMPT_POWER_UNIT, power_unit_keyboard()))


@router.message(CalcStates.power_unit)
@with_nav
async def get_power_unit(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip().lower()
    if choice not in {"hp", "kw"}:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=power_unit_keyboard())
        return
    await state.update_data(power_unit=choice)
    await nav.push(message, state, NavStep(CalcStates.power, PROMPT_POWER, back_menu()))


@router.message(CalcStates.power)
@with_nav
async def get_power(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    data = await state.get_data()
    if data.get("power_unit") not in {"hp", "kw"}:
        await nav.push(message, state, NavStep(CalcStates.power_unit, PROMPT_POWER_UNIT, power_unit_keyboard()))
        return
    try:
        power = int(message.text)
    except ValueError:
        await message.answer(ERROR_ENTER_NUMBER)
        return
    await state.update_data(power=power)
    await nav.push(message, state, NavStep(CalcStates.price, PROMPT_PRICE, back_menu()))


@router.message(CalcStates.price)
@with_nav
async def get_price(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(ERROR_REQ_PRICE)
        return
    await state.update_data(price=price)
    await nav.push(message, state, NavStep(CalcStates.owner, PROMPT_OWNER, owner_keyboard()))


@router.message(CalcStates.owner)
@with_nav
async def get_owner(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    choice = message.text.strip()
    if choice not in {"individual", "company"}:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=owner_keyboard())
        return
    await state.update_data(owner=choice)
    await nav.push(message, state, NavStep(CalcStates.currency, PROMPT_CURRENCY, currency_keyboard()))


@router.message(CalcStates.currency)
@with_nav
async def finish_calc(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    data = await state.get_data()
    currency = message.text.strip().upper()
    if currency not in {"USD", "EUR"}:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=currency_keyboard())
        return
    data.update(currency=currency)

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


@router.message(CalcStates.older_than_3)
@with_nav
async def confirm_older3(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    ans = message.text.strip().lower()
    valid_yes = {"yes", "да", "da"}
    valid_no = {"no", "нет", "net"}
    if ans not in (valid_yes | valid_no):
        await message.answer(ERROR_SELECT_YES_NO, reply_markup=yes_no_keyboard())
        return
    age_bucket = "3-5" if ans in valid_yes else "1-3"
    await state.update_data(age=age_bucket)
    await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))


@router.message(CalcStates.older_than_5)
@with_nav
async def confirm_older5(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    ans = message.text.strip().lower()
    valid_yes = {"yes", "да", "da"}
    valid_no = {"no", "нет", "net"}
    if ans not in (valid_yes | valid_no):
        await message.answer(ERROR_SELECT_YES_NO, reply_markup=yes_no_keyboard())
        return
    age_bucket = "5-7" if ans in valid_yes else "3-5"
    await state.update_data(age=age_bucket)
    await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))

