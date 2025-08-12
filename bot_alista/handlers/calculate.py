"""Handlers for customs cost calculation."""

from __future__ import annotations

import logging
from datetime import date
from typing import List

from aiogram import F, Router, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from states import CalculationStates
from keyboards.navigation import back_menu
from utils.reset import reset_to_menu
from bot_alista.services.rates import get_cached_rates, currency_to_rub
from tariff_engine import calc_import_breakdown
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG

router = Router()

# Navigation text constants
BACK_TEXT = "⬅ Назад"
MENU_TEXT = "🏠 Главное меню"

# Currency constants
CURRENCY_EUR = "EUR"
CURRENCY_USD = "USD"
CURRENCY_JPY = "JPY"
CURRENCY_CNY = "CNY"
CURRENCIES: List[str] = [CURRENCY_EUR, CURRENCY_USD, CURRENCY_JPY, CURRENCY_CNY]


def car_type_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Бензин"), types.KeyboardButton(text="Дизель")],
            [types.KeyboardButton(text="Гибрид"), types.KeyboardButton(text="Электро")],
            [types.KeyboardButton(text=MENU_TEXT)],
        ],
        resize_keyboard=True,
    )


def currency_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=CURRENCY_EUR), types.KeyboardButton(text=CURRENCY_USD)],
            [types.KeyboardButton(text=CURRENCY_JPY), types.KeyboardButton(text=CURRENCY_CNY)],
            [types.KeyboardButton(text=BACK_TEXT), types.KeyboardButton(text=MENU_TEXT)],
        ],
        resize_keyboard=True,
    )


def _is_menu(text: str | None) -> bool:
    return (text or "").lower() in {MENU_TEXT.lower(), "главное меню"}


async def _check_menu(message: types.Message, state: FSMContext) -> bool:
    if _is_menu(message.text):
        await reset_to_menu(message, state)
        return True
    return False


@router.message(F.text == "📊 Рассчитать стоимость таможенной очистки")
async def start_calculation(message: types.Message, state: FSMContext) -> None:
    await state.set_state(CalculationStates.calc_type)
    await message.answer("Выберите тип авто:", reply_markup=car_type_kb())


@router.message(CalculationStates.calc_type)
async def get_car_type(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    if message.text not in ["Бензин", "Дизель", "Гибрид", "Электро"]:
        await message.answer("Пожалуйста, выберите тип авто кнопкой.")
        return
    await state.update_data(car_type=message.text)
    await state.set_state(CalculationStates.calc_currency)
    await message.answer("Выберите валюту цены:", reply_markup=currency_kb())


@router.message(CalculationStates.calc_currency)
async def get_currency(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    if message.text == BACK_TEXT:
        await state.set_state(CalculationStates.calc_type)
        await message.answer("Выберите тип авто:", reply_markup=car_type_kb())
        return
    if message.text not in CURRENCIES:
        await message.answer("Пожалуйста, выберите валюту кнопкой.")
        return
    await state.update_data(currency_code=message.text)
    await state.set_state(CalculationStates.calc_price)
    await message.answer("Введите стоимость авто:", reply_markup=back_menu())


@router.message(CalculationStates.calc_price)
async def get_price(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    if message.text == BACK_TEXT:
        await state.set_state(CalculationStates.calc_currency)
        await message.answer("Выберите валюту цены:", reply_markup=currency_kb())
        return
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введите корректную стоимость.")
        return
    await state.update_data(price=price)
    data = await state.get_data()
    if data["car_type"] != "Электро":
        await state.set_state(CalculationStates.calc_engine)
        await message.answer("Введите объём двигателя (см³):", reply_markup=back_menu())
    else:
        await state.set_state(CalculationStates.calc_power)
        await message.answer("Введите мощность двигателя (л.с. или кВт):", reply_markup=back_menu())


@router.message(CalculationStates.calc_engine)
async def get_engine(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    if message.text == BACK_TEXT:
        await state.set_state(CalculationStates.calc_price)
        await message.answer("Введите стоимость авто:", reply_markup=back_menu())
        return
    try:
        engine = int(message.text)
    except ValueError:
        await message.answer("Введите корректный объём двигателя в см³.")
        return
    await state.update_data(engine=engine)
    await state.set_state(CalculationStates.calc_power)
    await message.answer("Введите мощность двигателя (л.с. или кВт):", reply_markup=back_menu())


@router.message(CalculationStates.calc_power)
async def get_power(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    data = await state.get_data()
    if message.text == BACK_TEXT:
        if data["car_type"] != "Электро":
            await state.set_state(CalculationStates.calc_engine)
            await message.answer("Введите объём двигателя (см³):", reply_markup=back_menu())
        else:
            await state.set_state(CalculationStates.calc_price)
            await message.answer("Введите стоимость авто:", reply_markup=back_menu())
        return
    try:
        val = message.text.lower().replace(",", ".")
        if "квт" in val or "kw" in val:
            power_kw = float("".join(c for c in val if c.isdigit() or c == "."))
            power_hp = power_kw * 1.35962
        else:
            power_hp = float("".join(c for c in val if c.isdigit() or c == "."))
    except Exception:
        await message.answer("Введите корректную мощность (пример: 150 или 110 кВт).")
        return
    await state.update_data(power_hp=round(power_hp, 1))
    await state.set_state(CalculationStates.calc_year)
    await message.answer("Введите год выпуска авто:", reply_markup=back_menu())


@router.message(CalculationStates.calc_year)
async def get_year(message: types.Message, state: FSMContext) -> None:
    if await _check_menu(message, state):
        return
    if message.text == BACK_TEXT:
        await state.set_state(CalculationStates.calc_power)
        await message.answer("Введите мощность двигателя (л.с. или кВт):", reply_markup=back_menu())
        return
    try:
        year = int(message.text)
        if year < 1980 or year > date.today().year + 1:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректный год выпуска.")
        return
    await state.update_data(year=year)
    await run_calculation(state, message)


async def run_calculation(state: FSMContext, message: types.Message) -> None:
    data = await state.get_data()
    try:
        decl_date = date.today()
        amount = data["price"]
        currency_code = data["currency_code"]

        rates = get_cached_rates(decl_date, codes=CURRENCIES)
        customs_value_rub = currency_to_rub(amount, currency_code, decl_date)
        eur_rate = rates[CURRENCY_EUR]
        customs_value_eur = round(customs_value_rub / eur_rate, 2)

        engine_cc = int(data.get("engine", 0))
        engine_hp = int(data.get("power_hp", 0))
        year = data.get("year")
        age_years = decl_date.year - year if year else 0

        car_type = data.get("car_type", "Бензин")
        fuel_type = "ice"
        if car_type == "Электро":
            fuel_type = "ev"
            engine_cc = 0
        elif car_type == "Гибрид":
            fuel_type = "hybrid"

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
            f"Цена: {amount} {currency_code}\n"
            f"Курсы: {currency_code}={rates[currency_code]} | EUR={eur_rate}\n"
            f"Таможенная стоимость: {customs_value_rub} ₽\n"
            f"Пошлина: {core['breakdown']['duty_eur']} € / {core['breakdown']['duty_rub']} ₽\n"
            f"Акциз: {core['breakdown']['excise_rub']} ₽\n"
            f"НДС: {core['breakdown']['vat_rub']} ₽\n"
            f"Утиль: {util} ₽\n"
            f"ИТОГО: {total} ₽\n"
            f"Примечания: {notes}\n"
            "```"
        )
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:  # pragma: no cover - runtime errors
        logging.exception("Calculation failed: %s", exc)
        await message.answer("❌ Произошла ошибка при расчёте. Попробуйте позже.")
    finally:
        await reset_to_menu(message, state)
