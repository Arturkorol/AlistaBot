"""FSM states for customs calculation flow."""

from aiogram.fsm.state import State, StatesGroup


class CalculationStates(StatesGroup):
    """Conversation steps for vehicle customs calculation."""

    calc_type = State()
    currency_code = State()
    customs_value_amount = State()
    calc_engine = State()
    calc_power = State()
    calc_year = State()
    calc_weight = State()
    manual_rate = State()
