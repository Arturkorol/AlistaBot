"""FSM state groups for bot conversations."""

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


class RequestStates(StatesGroup):
    """Conversation steps for submitting a customs request."""

    request_name = State()
    request_car = State()
    request_contact = State()
    request_price = State()
    request_comment = State()


__all__ = ["CalculationStates", "RequestStates"]
