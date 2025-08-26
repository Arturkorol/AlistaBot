"""Vehicle customs calculation conversation handlers."""

from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot_alista.states import CalculationStates
from bot_alista.keyboards.navigation import back_menu
from bot_alista.constants import (
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
    BTN_FAQ,
    BTN_CALC,
    BTN_METHOD_ETC,
    BTN_METHOD_CTP,
    BTN_METHOD_AUTO,
    PROMPT_METHOD,
)
from bot_alista.utils.navigation import NavigationManager, NavStep
from bot_alista.services.rates import get_cached_rates
from bot_alista.formatting import format_result_message
from bot_alista.services.customs_calculator import (
    CustomsCalculator,
    EngineType,
    VehicleAge,
)
from bot_alista.keyboards.calculation import (
    person_type_kb,
    usage_type_kb,
    car_type_kb,
    currency_kb,
    age_over3_kb,
    method_type_kb,
)
from bot_alista.rules.age import compute_actual_age_years
from bot_alista.handlers.faq import show_faq

router = Router()


# Map Russian fuel type labels to EngineType enum
ENGINE_TYPE_LABELS = {
    "Бензин": EngineType.GASOLINE,
    "Дизель": EngineType.DIESEL,
    "Гибрид": EngineType.HYBRID,
    "Электро": EngineType.ELECTRIC,
}


async def _handle_faq_and_nav(
    message: types.Message, state: FSMContext, nav: NavigationManager | None
) -> bool:
    """Handle FAQ requests and navigation commands.

    Returns ``True`` if the caller should exit early.
    """
    if message.text == BTN_FAQ:
        await show_faq(message, state)
        return True
    if nav and await nav.handle_nav(message, state):
        return True
    return False

# ---------------------------------------------------------------------------
# Conversation steps
# ---------------------------------------------------------------------------


@router.message(lambda msg: msg.text.casefold() == BTN_CALC.casefold())
async def start_calculation(message: types.Message, state: FSMContext) -> None:
    nav = NavigationManager(total_steps=10)  # теперь 10 шагов
    await state.update_data(_nav=nav)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.method_choice, PROMPT_METHOD, method_type_kb()),
    )


@router.message(Command("customs"))
async def customs_command(message: types.Message, state: FSMContext) -> None:
    await start_calculation(message, state)

@router.message(CalculationStates.method_choice)
async def get_method_choice(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if message.text not in {BTN_METHOD_ETC, BTN_METHOD_CTP, BTN_METHOD_AUTO}:
        await message.answer(PROMPT_METHOD)
        return
    if message.text == BTN_METHOD_ETC:
        method = "ETC"
    elif message.text == BTN_METHOD_CTP:
        method = "CTP"
    else:
        method = "AUTO"
    await state.update_data(method=method)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.person_type, PROMPT_PERSON, person_type_kb()),
    )

@router.message(CalculationStates.person_type)
async def get_person_type(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    if message.text not in {"Физическое лицо", "Юридическое лицо"}:
        await message.answer(ERROR_PERSON)
        return
    await state.update_data(person_type=message.text)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.usage_type, PROMPT_USAGE, usage_type_kb()),
    )


@router.message(CalculationStates.usage_type)
async def get_usage_type(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    if message.text not in {"Личное", "Коммерческое"}:
        await message.answer(ERROR_USAGE)
        return
    await state.update_data(usage_type=message.text)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.calc_type, PROMPT_TYPE, car_type_kb()),
    )


@router.message(CalculationStates.calc_type)
async def get_car_type(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    if message.text not in {"Бензин", "Дизель", "Гибрид", "Электро"}:
        await message.answer(ERROR_TYPE)
        return
    await state.update_data(car_type=message.text)
    if message.text == "Электро":
        nav.total_steps = 8
    else:
        nav.total_steps = 9
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.currency_code, PROMPT_CURRENCY, currency_kb()),
    )


@router.message(CalculationStates.currency_code)
async def choose_currency(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    if message.text not in CURRENCY_CODES:
        await message.answer(ERROR_CURRENCY)
        return
    await state.update_data(currency_code=message.text)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.customs_value_amount, PROMPT_AMOUNT, back_menu()),
    )


@router.message(CalculationStates.customs_value_amount)
async def get_amount(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    try:
        amount = float(message.text.replace(",", "."))
    except Exception:
        await message.answer(ERROR_AMOUNT)
        return
    await state.update_data(amount=amount)
    if data.get("car_type") != "Электро":
        await nav.push(
            message,
            state,
            NavStep(CalculationStates.calc_engine, PROMPT_ENGINE, back_menu()),
        )
    else:
        await state.update_data(engine=0)
        await nav.push(
            message,
            state,
            NavStep(CalculationStates.calc_power, PROMPT_POWER, back_menu()),
        )


@router.message(CalculationStates.calc_engine)
async def get_engine(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    try:
        engine = int(message.text)
    except Exception:
        await message.answer(ERROR_ENGINE)
        return
    await state.update_data(engine=engine)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.calc_power, PROMPT_POWER, back_menu()),
    )


@router.message(CalculationStates.calc_power)
async def get_power(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
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
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.calc_year, PROMPT_YEAR, back_menu()),
    )


@router.message(CalculationStates.calc_year)
async def get_year(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    try:
        year = int(message.text)
        if year < 1980 or year > date.today().year:
            raise ValueError
    except Exception:
        await message.answer(ERROR_YEAR)
        return
    await state.update_data(year=year)
    await nav.push(
        message,
        state,
        NavStep(CalculationStates.age_over_3, PROMPT_AGE_OVER3, age_over3_kb()),
    )


@router.message(CalculationStates.age_over_3)
async def handle_age_over3(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    nav: NavigationManager | None = data.get("_nav")
    if await _handle_faq_and_nav(message, state, nav):
        return
    if message.text not in {BTN_AGE_OVER3_YES, BTN_AGE_OVER3_NO}:
        await message.answer(PROMPT_AGE_OVER3, reply_markup=age_over3_kb())
        return
    over3 = message.text == BTN_AGE_OVER3_YES
    age_years = 4.0 if over3 else 2.0
    await state.update_data(age_years=age_years, age_over_3=over3)

    # Hide the age keyboard immediately
    await message.answer("Принято ✅", reply_markup=types.ReplyKeyboardRemove())

    await _run_calculation(state, message)

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------


async def _run_calculation(state: FSMContext, message: types.Message) -> None:
    data = await state.get_data()
    try:
        car_type_ru: str = data["car_type"]
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
        try:
            non_rub = [c for c in CURRENCY_CODES if c != "RUB"]
            rates = await get_cached_rates(decl_date, codes=non_rub)
            rates["RUB"] = 1.0
        except Exception:
            await message.answer(
                "Не удалось получить курсы ЦБ РФ, попробуйте позже",
                reply_markup=back_menu(),
            )
            await state.clear()
            return

        engine_type = ENGINE_TYPE_LABELS.get(car_type_ru, EngineType.GASOLINE)
        age_over_3 = bool(data.get("age_over_3", False))

        actual_age = compute_actual_age_years(year, decl_date)
        if actual_age < 1:
            age_enum = VehicleAge.NEW
        elif actual_age <= 3:
            age_enum = VehicleAge.ONE_TO_THREE
        elif actual_age <= 5:
            age_enum = VehicleAge.THREE_TO_FIVE
        elif actual_age <= 7:
            age_enum = VehicleAge.FIVE_TO_SEVEN
        else:
            age_enum = VehicleAge.OVER_SEVEN
        age_group = age_enum.value
        calc = CustomsCalculator("external/tks_api_official/config.yaml")
        calc.set_vehicle_details(
            age=age_group,
            engine_capacity=engine_cc,
            engine_type=engine_type,
            power=engine_hp,
            price=amount,
            owner_type=person_type,
            currency=currency_code,
        )
        method = data.get("method")
        if method == "ETC":
            breakdown = calc.calculate_etc()
        elif method == "CTP":
            breakdown = calc.calculate_ctp()
        else:  # AUTO or unspecified
            breakdown = calc.calculate_auto()

        price_rub = calc.convert_to_local_currency(calc.vehicle_price, calc.vehicle_currency)
        if "Price (RUB)" in breakdown:
            core_breakdown = {
                "customs_value_rub": breakdown["Price (RUB)"],
                "duty_rub": breakdown["Duty (RUB)"],
                "excise_rub": breakdown.get("Excise (RUB)", 0.0),
                "vat_rub": breakdown.get("VAT (RUB)", 0.0),
                "clearance_fee_rub": breakdown["Clearance Fee (RUB)"],
                "util_rub": breakdown["Util Fee (RUB)"],
                "recycling_rub": 0.0,
                "total_rub": breakdown["Total Pay (RUB)"],
            }
        else:
            core_breakdown = {
                "customs_value_rub": price_rub,
                "duty_rub": breakdown["Duty (RUB)"],
                "excise_rub": 0.0,
                "vat_rub": 0.0,
                "clearance_fee_rub": breakdown["Clearance Fee (RUB)"],
                "util_rub": breakdown["Util Fee (RUB)"],
                "recycling_rub": breakdown["Recycling Fee (RUB)"],
                "total_rub": breakdown["Total Pay (RUB)"],
            }
        core = {
            "breakdown": core_breakdown,
            "notes": [],
        }

        duty_rub = core["breakdown"]["duty_rub"]
        rate_line = ""
        if duty_rub and engine_cc:
            try:
                rate_rub_per_cc = round(float(duty_rub) / float(engine_cc), 2)
                rate_line = f"{rate_rub_per_cc} ₽/см³ × {engine_cc} см³"
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
        await message.answer(
            msg,
            disable_web_page_preview=True,
            reply_markup=back_menu(),
        )
        await state.clear()
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Calculation failed: %s", exc)
        await message.answer("❌ Ошибка расчёта. Проверьте введённые данные.")
        await state.clear()

