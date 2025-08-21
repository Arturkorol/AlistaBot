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
    PROMPT_PERSON,
    ERROR_PERSON,
    PROMPT_USAGE,
    ERROR_USAGE,
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
    PROMPT_AGE_OVER3,
    BTN_AGE_OVER3_YES,
    BTN_AGE_OVER3_NO,
    BTN_BACK,
    ERROR_RATE,
)
from bot_alista.services.rates import (
    get_cached_rates,
    validate_or_prompt_rate,
)
from tariff_engine import calc_breakdown_rules
from bot_alista.formatting import format_result_message


router = Router()


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def _person_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [
            types.KeyboardButton(text="Физическое лицо"),
            types.KeyboardButton(text="Юридическое лицо"),
        ],
        [types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _usage_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text="Личное"), types.KeyboardButton(text="Коммерческое")],
        [types.KeyboardButton(text="⬅ Назад"), types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _car_type_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text="Бензин"), types.KeyboardButton(text="Дизель")],
        [types.KeyboardButton(text="Гибрид"), types.KeyboardButton(text="Электро")],
        [types.KeyboardButton(text="⬅ Назад"), types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _currency_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text=CURRENCY_CODES[0]), types.KeyboardButton(text=CURRENCY_CODES[1])],
        [types.KeyboardButton(text=CURRENCY_CODES[2]), types.KeyboardButton(text=CURRENCY_CODES[3])],
        [types.KeyboardButton(text="⬅ Назад"), types.KeyboardButton(text="🏠 Главное меню")],
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _age_over3_kb() -> types.ReplyKeyboardMarkup:
    kb = [
        [types.KeyboardButton(text=BTN_AGE_OVER3_YES), types.KeyboardButton(text=BTN_AGE_OVER3_NO)],
        [types.KeyboardButton(text=BTN_BACK)],
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
    await state.set_state(CalculationStates.person_type)
    await message.answer(PROMPT_PERSON, reply_markup=_person_type_kb())


@router.message(CalculationStates.person_type)
async def get_person_type(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(message, state, None, None, None):
        return
    if message.text not in {"Физическое лицо", "Юридическое лицо"}:
        await message.answer(ERROR_PERSON)
        return
    await state.update_data(person_type=message.text)
    await state.set_state(CalculationStates.usage_type)
    await message.answer(PROMPT_USAGE, reply_markup=_usage_type_kb())


@router.message(CalculationStates.usage_type)
async def get_usage_type(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.person_type, PROMPT_PERSON, _person_type_kb()
    ):
        return
    if message.text not in {"Личное", "Коммерческое"}:
        await message.answer(ERROR_USAGE)
        return
    await state.update_data(usage_type=message.text)
    await state.set_state(CalculationStates.calc_type)
    await message.answer(PROMPT_TYPE, reply_markup=_car_type_kb())


@router.message(CalculationStates.calc_type)
async def get_car_type(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message,
        state,
        CalculationStates.usage_type,
        PROMPT_USAGE,
        _usage_type_kb(),
    ):
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
    await state.set_state(CalculationStates.age_over_3)
    await message.answer(PROMPT_AGE_OVER3, reply_markup=_age_over3_kb())


@router.message(
    CalculationStates.age_over_3, F.text.in_({BTN_AGE_OVER3_YES, BTN_AGE_OVER3_NO})
)
async def on_age_over_3_choice(message: types.Message, state: FSMContext) -> None:
    over3 = message.text == BTN_AGE_OVER3_YES
    age_years = 4.0 if over3 else 2.0
    await state.update_data(age_years=age_years, age_over_3=over3)

    # Hide the age keyboard immediately
    await message.answer("Принято ✅", reply_markup=types.ReplyKeyboardRemove())

    await _run_calculation(state, message)


@router.message(CalculationStates.age_over_3, F.text == BTN_BACK)
async def on_age_over_3_back(message: types.Message, state: FSMContext) -> None:
    await message.answer(PROMPT_YEAR, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CalculationStates.calc_year)


@router.message(CalculationStates.age_over_3)
async def on_age_over_3_invalid(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.calc_year, PROMPT_YEAR, back_menu()
    ):
        return
    await message.answer(PROMPT_AGE_OVER3, reply_markup=_age_over3_kb())


@router.message(CalculationStates.manual_rate)
async def get_manual_rate(message: types.Message, state: FSMContext) -> None:
    if await _check_nav(
        message, state, CalculationStates.age_over_3, PROMPT_AGE_OVER3, _age_over3_kb()
    ):
        return
    data = await state.get_data()
    code = data.get("pending_rate_code")
    try:
        rate = validate_or_prompt_rate(message.text)
    except ValueError:
        await message.answer(ERROR_RATE)
        return
    manual_rates = data.get("manual_rates", {})
    manual_rates[code] = rate
    await state.update_data(manual_rates=manual_rates)
    needed = {data.get("currency_code"), "EUR"}
    missing = [c for c in needed if c not in manual_rates]
    if missing:
        next_code = missing[0]
        await state.update_data(pending_rate_code=next_code)
        await message.answer(
            f"📥 Введите курс {next_code} вручную (₽ за {next_code}):",
            reply_markup=back_menu(),
        )
        return
    await _run_calculation(state, message)

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
        person_ru: str = data.get("person_type", "Физическое лицо")
        usage_ru: str = data.get("usage_type", "Личное")

        person_type = "individual" if person_ru == "Физическое лицо" else "company"
        usage_type = "personal" if usage_ru == "Личное" else "commercial"

        decl_date = data.get("decl_date") or date.today()
        manual_rates = data.get("manual_rates", {})
        needed = {currency_code, "EUR"}
        try:
            rates = get_cached_rates(decl_date, codes=("EUR", "USD", "JPY", "CNY"))
            customs_value_rub = amount * rates[currency_code]
        except Exception:
            missing = [c for c in needed if c not in manual_rates]
            if missing:
                await state.update_data(pending_rate_code=missing[0])
                await state.set_state(CalculationStates.manual_rate)
                await message.answer(
                    f"📥 Введите курс {missing[0]} вручную (₽ за {missing[0]}):",
                    reply_markup=back_menu(),
                )
                return
            rates = manual_rates
            customs_value_rub = amount * rates[currency_code]
        eur_rate = rates["EUR"]
        customs_value_eur = round(customs_value_rub / eur_rate, 2)

        fuel_type = car_type
        age_over_3 = bool(data.get("age_over_3", False))

        core = calc_breakdown_rules(
            person_type=person_type,
            usage_type=usage_type,
            customs_value_eur=customs_value_eur,
            eur_rub_rate=eur_rate,
            engine_cc=engine_cc,
            engine_hp=engine_hp,
            production_year=year,
            age_choice_over3=age_over_3,
            fuel_type=fuel_type,
            decl_date=decl_date,
        )

        duty_eur = core["breakdown"].get("duty_eur")
        rate_line = ""
        if duty_eur and engine_cc:
            try:
                rate_eur_per_cc = round(float(duty_eur) / float(engine_cc), 2)
                rate_line = f"{rate_eur_per_cc} €/см³ × {engine_cc} см³"
            except Exception:
                rate_line = ""

        meta = {
            "person_usage": (
                "Тип лица: Физическое, личное использование"
                if person_type == "individual" and usage_type == "personal"
                else "Тип лица: Юридическое / коммерческое использование"
            ),
            "age_info": "Выбор для пошлины (ФЛ): "
            + ("старше 3 лет" if age_over_3 else "не старше 3 лет")
            if person_type == "individual" and usage_type == "personal"
            else "",
            "util_age_info": "",
            "duty_rate_info": rate_line,
            "extra_notes": core.get("notes", []),
        }

        msg = format_result_message(
            currency_code=currency_code,
            price_amount=amount,
            rates=rates,
            meta=meta,
            core=core,
            util_fee_rub=core["breakdown"].get("util_rub", 0.0),
        )
        await message.answer(msg, disable_web_page_preview=True)
        await state.clear()
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Calculation failed: %s", exc)
        await message.answer("❌ Ошибка расчёта. Проверьте введённые данные.")
        await state.clear()

