"""FSM states for customs calculation flow."""

from aiogram.fsm.state import State, StatesGroup


class CalculationStates(StatesGroup):
    """Conversation steps for vehicle customs calculation."""

    person_type = State()
    usage_type = State()
    calc_type = State()
    currency_code = State()
    customs_value_amount = State()
    calc_engine = State()
    calc_power = State()
    calc_year = State()
    age_over_3 = State()
    manual_rate = State()
