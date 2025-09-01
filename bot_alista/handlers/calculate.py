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
    PROMPT_HYBRID_TYPE,
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
    hybrid_type_keyboard,
    owner_keyboard,
    currency_keyboard,
    power_unit_keyboard,
    yes_no_keyboard,
)
from bot_alista.states.calc import CalcStates
from bot_alista.services.unified_calc import UnifiedCalculator
from bot_alista.services.pdf_report import generate_calculation_pdf
from bot_alista.services.rates import get_rates
from bot_alista.utils.reset import reset_to_menu
from bot_alista.utils.formatting import format_result_message
from bot_alista.settings import settings
from decimal import Decimal
from bot_alista.models.constants import SUPPORTED_CURRENCY_CODES


router = Router()


@router.message(F.text == BTN_CALC)
async def start_calc(message: types.Message, state: FSMContext):
    nav = NavigationManager(total_steps=10)
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
    raw = (message.text or "").strip().lower()
    mapping = {
        "gasoline": "gasoline",
        "\u26fd \u0431\u0435\u043d\u0437\u0438\u043d": "gasoline",  # ? бензин
        "\u0431\u0435\u043d\u0437\u0438\u043d": "gasoline",
        "diesel": "diesel",
        "\\U0001F6E2\ufe0f \u0434\u0438\u0437\u0435\u043b\u044c": "diesel",  # ??? дизель
        "\u0434\u0438\u0437\u0435\u043b\u044c": "diesel",
        "electric": "electric",
        "\\U0001F50C \u044d\u043b\u0435\u043a\u0442\u0440\u043e": "electric",  # ?? электро
        "\u044d\u043b\u0435\u043a\u0442\u0440\u043e": "electric",
        "hybrid": "hybrid",
        "\u267b\ufe0f \u0433\u0438\u0431\u0440\u0438\u0434": "hybrid",  # ?? гибрид
        "\u0433\u0438\u0431\u0440\u0438\u0434": "hybrid",
    }
    mapping.update({
        "\U0001F6E2\ufe0f \u0434\u0438\u0437\u0435\u043b\u044c": "diesel",
        "\U0001F50C \u044d\u043b\u0435\u043a\u0442\u0440\u043e": "electric",
    })
    choice = mapping.get(raw)
    if not choice:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=engine_keyboard())
        return
    await state.update_data(engine=choice)
    if choice == "hybrid":
        await nav.push(message, state, NavStep(CalcStates.hybrid_type, PROMPT_HYBRID_TYPE, hybrid_type_keyboard()))
        return
    await nav.push(message, state, NavStep(CalcStates.engine_capacity, PROMPT_ENGINE_CAPACITY, back_menu()))


@router.message(CalcStates.hybrid_type)
@with_nav
async def get_hybrid_type(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    raw = (message.text or "").strip().lower()
    import re
    norm = re.sub(r"[^a-z\u0430-\u044f\u0451\s]+", " ", raw, flags=re.IGNORECASE).strip()
    mapping = {
        "\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u044b\u0439 \u0433\u0438\u0431\u0440\u0438\u0434": "parallel",
        "\u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u044b\u0439": "parallel",
        "parallel": "parallel",
        "\u0441\u0435\u0440\u0438\u0439\u043d\u044b\u0439 \u0433\u0438\u0431\u0440\u0438\u0434": "series",
        "\u0441\u0435\u0440\u0438\u0439\u043d\u044b\u0439": "series",
        "series": "series",
    }
    subtype = mapping.get(norm)
    if not subtype:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=hybrid_type_keyboard())
        return
    await state.update_data(hybrid_subtype=subtype)
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
    raw = (message.text or "").strip().lower()
    if "\u043b.\u0441" in raw or raw == "hp":  # л.с. or HP
        choice = "hp"
    elif "\u043a\u0432\u0442" in raw or raw == "kw":  # кВт or kW
        choice = "kw"
    else:
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
    import re
    raw = (message.text or "").strip().lower()
    # Strip emojis/punctuation to improve matching
    norm = re.sub(r"[^a-zа-яё]+", " ", raw, flags=re.IGNORECASE).strip()
    owner = None
    if "физ" in norm:
        owner = "individual"
    elif "юр" in norm:
        owner = "company"
    elif norm in {"individual", "company"}:
        owner = norm
    if not owner:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=owner_keyboard())
        return
    await state.update_data(owner=owner)
    await nav.push(message, state, NavStep(CalcStates.currency, PROMPT_CURRENCY, currency_keyboard()))


@router.message(CalcStates.currency)
@with_nav
async def finish_calc(message: types.Message, state: FSMContext, nav: NavigationManager | None):
    data = await state.get_data()
    raw = (message.text or "").upper()
    currency = next((code for code in SUPPORTED_CURRENCY_CODES if code in raw), None)
    if not currency:
        await message.answer(ERROR_SELECT_FROM_KEYBOARD, reply_markup=currency_keyboard())
        return
    data.update(currency=currency)

    tariffs = (settings.tariff_config or {}).get("tariffs", {})
    base_cur = str(tariffs.get("currency", "EUR")).upper()
    wanted = sorted(set([currency, base_cur, *SUPPORTED_CURRENCY_CODES]))
    rates = await get_rates(wanted)
    try:
        facade = UnifiedCalculator(settings, rates)
        form = {
            "age": data["age"],
            "engine": data["engine"],
            "capacity": data["capacity"],
            "power": data["power"],
            "owner": data["owner"],
            "currency": currency,
            "price": data["price"],
            "power_unit": data.get("power_unit", "hp"),
            "hybrid_subtype": data.get("hybrid_subtype"),
        }
        uni = facade.calculate(form)
        customs_value = uni["customs_value_rub"]
        duty_rub = uni["duty_rub"]
        excise_rub = uni["excise_rub"]
        vat_rub = uni["vat_rub"]
        util_rub = uni["util_rub"]
        clearance_fee_rub = uni["clearance_fee_rub"]
        total_with_util_rub = uni["total_with_util_rub"]
    except Exception as e:
        await message.answer(f"\u26a0\ufe0f \u041e\u0448\u0438\u0431\u043a\u0430 \u0440\u0430\u0441\u0447\u0451\u0442\u0430: {e}")
        await reset_to_menu(message, state)
        return

    eur_rate = rates.get("EUR")
    price_eur_val = None
    if eur_rate:
        if currency == "EUR":
            price_eur_val = data["price"]
        else:
            cur_rate = rates.get(currency)
            if cur_rate and eur_rate:
                price_eur_val = data["price"] * (cur_rate / eur_rate)
    breakdown = {
        "customs_value_rub": customs_value,
        "duty_rub": duty_rub,
        "clearance_fee_rub": clearance_fee_rub,
        "excise_rub": excise_rub,
        "vat_rub": vat_rub,
        "util_rub": util_rub,
        "total_rub": (duty_rub + excise_rub + vat_rub + clearance_fee_rub),
        "total_with_util_rub": total_with_util_rub,
    }
    # util_fee_rub for formatter
    util_fee_val_for_fmt = util_rub

    text = format_result_message(
        currency_code=currency,
        price_amount=data["price"],
        rates=rates,
        meta={},
        core={"breakdown": breakdown},
        util_fee_rub=util_fee_val_for_fmt,
    )
    await message.answer(text)

    pdf_path = f"calc_report_{uuid.uuid4().hex}.pdf"
    # Build a results-like dict for PDF using our computed values
    pdf_results = {
        "Duty (RUB)": float(duty_rub),
        "Excise (RUB)": float(excise_rub),
        "VAT (RUB)": float(vat_rub),
        "Clearance Fee (RUB)": float(clearance_fee_rub),
        "Util Fee (RUB)": float(util_rub),
        "Total Pay (RUB)": float(total_with_util_rub),
    }
    if eur_rate:
        pdf_results["eur_rate"] = eur_rate
        if price_eur_val is not None:
            pdf_results["price_eur"] = price_eur_val
    generate_calculation_pdf(pdf_results, data, pdf_path)
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
    if ans == "\u0434\u0430":
        ans = "yes"
    elif ans == "\u043d\u0435\u0442":
        ans = "no"
    valid_yes = {"yes", "da", "\u0434\u0430"}
    valid_no = {"no", "net", "\u043d\u0435\u0442"}
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
    if ans == "\u0434\u0430":
        ans = "yes"
    elif ans == "\u043d\u0435\u0442":
        ans = "no"
    valid_yes = {"yes", "da", "\u0434\u0430"}
    valid_no = {"no", "net", "\u043d\u0435\u0442"}
    if ans not in (valid_yes | valid_no):
        await message.answer(ERROR_SELECT_YES_NO, reply_markup=yes_no_keyboard())
        return
    age_bucket = "5-7" if ans in valid_yes else "3-5"
    await state.update_data(age=age_bucket)
    await nav.push(message, state, NavStep(CalcStates.engine_type, PROMPT_ENGINE_TYPE, engine_keyboard()))
