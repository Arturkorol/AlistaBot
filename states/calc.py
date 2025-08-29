from aiogram.fsm.state import State, StatesGroup


class CalcStates(StatesGroup):
    year = State()
    older_than_3 = State()
    older_than_5 = State()
    age = State()
    engine_type = State()
    engine_capacity = State()
    power_unit = State()
    power = State()
    price = State()
    owner = State()
    currency = State()

__all__ = ["CalcStates"]

