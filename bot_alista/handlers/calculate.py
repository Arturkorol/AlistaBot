"""Vehicle customs calculation conversation handlers."""

from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State

from states import CalculationStates
from keyboards.navigation import back_menu
from utils.reset import reset_to_menu
from constants import (
    CURRENCY_CODES,
    PROMPT_TYPE,
    ERROR_TYPE,
    PROMPT_CURRENCY,
    ERROR_CURRENCY,
    PROMPT_AMOUNT,
    ERROR_AMOUNT,
    PROMPT_ENGINE,
    ERROR_ENGINE,
    PROMPT_POWER,
    ERROR_POWER,
    PROMPT_YEAR,
    ERROR_YEAR,
    PROMPT_WEIGHT,
    ERROR_WEIGHT,
)
from bot_alista.services.rates import get_cached_rates, currency_to_rub
from tariff_engine import calc_import_breakdown
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG


router = Router()


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def _car_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text="Бензин"), types.KeyboardButton(text="Дизель")],
        [types.KeyboardButton(text="Гибрид"), types.KeyboardButton(text="Электро")],
        [types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _currency_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text=CURRENCY_CODES[0]), types.KeyboardButton(text=CURRENCY_CODES[1])],
        [types.KeyboardButton(text=CURRENCY_CODES[2]), types.KeyboardButton(text=CURRENCY_CODES[3])],
        [types.KeyboardButton(text="⬅ Назад"), types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


async def _check_nav(
    message: types.Message,
    state: FSMContext,
    prev_state: State | None,
    prev_prompt: str | None,
    prev_kb: types.ReplyKeyboardMarkup | None,
) -> bool:
    """Handle navigation buttons. Return True if navigation occurred."""

    if message.text == "🏠 Главное меню":
        await reset_to_menu(message, state)
        return True
    if message.text == "⬅ Назад" and prev_state and prev_prompt and prev_kb:
        await state.set_state(prev_state)
        await message.answer(prev_prompt, reply_markup=prev_kb)
        return True
    return False


# ---------------------------------------------------------------------------
# Conversation steps
# ---------------------------------------------------------------------------


@router.message(F.text == "📊 Рассчитать стоимость таможенной очистки")
async def start_calculation(message: types.Message, state: FSMContext) -> None:
    await state.set_state(CalculationStates.calc_type)
    await message.answer(PROMPT_TYPE, reply_markup=_car_type_kb())


@router.message(CalculationStates.calc_type)
async def get_car_type(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(message, state, None, None, None):
        return
    if message.text not in {"Бензин", "Дизель", "Гибрид", "Электро"}:
        await message.answer(ERROR_TYPE)
        return
    await state.update_data(car_type=message.text)
    await state.set_state(CalculationStates.currency_code)
    await message.answer(PROMPT_CURRENCY, reply_markup=_currency_kb())


@router.message(CalculationStates.currency_code)
async def choose_currency(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.calc_type, PROMPT_TYPE, _car_type_kb()
    ):
        return
    if message.text not in CURRENCY_CODES:
        await message.answer(ERROR_CURRENCY)
        return
    await state.update_data(currency_code=message.text)
    await state.set_state(CalculationStates.customs_value_amount)
    await message.answer(PROMPT_AMOUNT, reply_markup=back_menu())


@router.message(CalculationStates.customs_value_amount)
async def get_amount(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.currency_code, PROMPT_CURRENCY, _currency_kb()
    ):
        return
    try:
        amount = float(message.text.replace(",", "."))
    except Exception:
        await message.answer(ERROR_AMOUNT)
        return
    await state.update_data(amount=amount)
    data = await state.get_data()
    if data.get("car_type") != "Электро":
        await state.set_state(CalculationStates.calc_engine)
        await message.answer(PROMPT_ENGINE, reply_markup=back_menu())
    else:
        await state.update_data(engine=0)
        await state.set_state(CalculationStates.calc_power)
        await message.answer(PROMPT_POWER, reply_markup=back_menu())


@router.message(CalculationStates.calc_engine)
async def get_engine(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message,
        state,
        CalculationStates.customs_value_amount,
        PROMPT_AMOUNT,
        back_menu(),
    ):
        return
    try:
        engine = int(message.text)
    except Exception:
        await message.answer(ERROR_ENGINE)
        return
    await state.update_data(engine=engine)
    await state.set_state(CalculationStates.calc_power)
    await message.answer(PROMPT_POWER, reply_markup=back_menu())


@router.message(CalculationStates.calc_power)
async def get_power(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    prev_state = CalculationStates.calc_engine if data.get("car_type") != "Электро" else CalculationStates.customs_value_amount
    prev_prompt = PROMPT_ENGINE if data.get("car_type") != "Электро" else PROMPT_AMOUNT
    prev_kb = back_menu()
    if await _check_nav(message, state, prev_state, prev_prompt, prev_kb):
        return
    try:
        val = message.text.lower().replace(",", ".")
        if "квт" in val or "kw" in val:
            power_kw = float("".join(c for c in val if c.isdigit() or c == "."))
            power_hp = power_kw * 1.35962
        else:
            power_hp = float("".join(c for c in val if c.isdigit() or c == "."))
    except Exception:
        await message.answer(ERROR_POWER)
        return
    await state.update_data(power_hp=round(power_hp, 1))
    await state.set_state(CalculationStates.calc_year)
    await message.answer(PROMPT_YEAR, reply_markup=back_menu())


@router.message(CalculationStates.calc_year)
async def get_year(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.calc_power, PROMPT_POWER, back_menu()
    ):
        return
    try:
        year = int(message.text)
        if year < 1980 or year > date.today().year:
            raise ValueError
    except Exception:
        await message.answer(ERROR_YEAR)
        return
    await state.update_data(year=year)
    await state.set_state(CalculationStates.calc_weight)
    await message.answer(PROMPT_WEIGHT, reply_markup=back_menu())


@router.message(CalculationStates.calc_weight)
async def get_weight(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.calc_year, PROMPT_YEAR, back_menu()
    ):
        return
    try:
        weight = int(message.text)
    except Exception:
        await message.answer(ERROR_WEIGHT)
        return
    await state.update_data(weight=weight)
    await _run_calculation(state, message)
    await state.clear()


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------


async def _run_calculation(state: FSMContext, message: types.Message) -> None:
    data = await state.get_data()
    try:
        car_type: str = data["car_type"]
        currency_code: str = data["currency_code"]
        amount: float = data["amount"]
        engine_cc: int = data.get("engine", 0)
        engine_hp: int = int(data.get("power_hp", 0))
        year: int = data["year"]

        decl_date = date.today()
        rates = get_cached_rates(decl_date, codes=CURRENCY_CODES)
        customs_value_rub = currency_to_rub(amount, currency_code, decl_date)
        eur_rate = rates["EUR"]
        customs_value_eur = round(customs_value_rub / eur_rate, 2)

        fuel_map = {
            "Бензин": "ice",
            "Дизель": "ice",
            "Гибрид": "hybrid",
            "Электро": "ev",
        }
        fuel_type = fuel_map.get(car_type, "ice")
        age_years = decl_date.year - year

        core = calc_import_breakdown(
            customs_value_eur=customs_value_eur,
            eur_rub_rate=eur_rate,
            engine_cc=engine_cc,
            engine_hp=engine_hp,
            is_disabled_vehicle=False,
            is_export=False,
            person_type="individual",
        )

        util = calc_util_rub(
            person_type="individual",
            usage="personal",
            engine_cc=engine_cc,
            fuel=fuel_type,
            vehicle_kind="passenger",
            age_years=age_years,
            date_decl=decl_date,
            avg_vehicle_cost_rub=None,
            actual_costs_rub=None,
            config=UTIL_CONFIG,
        )

        total = round(core["breakdown"]["total_rub"] + util, 2)
        notes = " | ".join(core.get("notes", []))

        text = (
            "```\n"
            f"Стоимость: {amount} {currency_code}\n"
            f"Курс {currency_code}: {rates[currency_code]:.2f}\n"
            f"Курс EUR: {eur_rate:.2f}\n"
            f"Тамож. стоимость: {customs_value_rub:.2f} ₽\n"
            f"Пошлина: {core['breakdown']['duty_eur']} € ({core['breakdown']['duty_rub']} ₽)\n"
            f"Акциз: {core['breakdown']['excise_rub']} ₽\n"
            f"НДС: {core['breakdown']['vat_rub']} ₽\n"
            f"Утильсбор: {util} ₽\n"
            f"ИТОГО: {total} ₽\n"
            f"Примечания: {notes}\n"
            "```"
        )
        await message.answer(text)
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Calculation failed: %s", exc)
        await message.answer("❌ Ошибка расчёта. Проверьте введённые данные.")

