from aiogram.fsm.state import State, StatesGroup


class RequestStates(StatesGroup):
    request_name = State()
    request_car = State()
    request_contact = State()
    request_price = State()
    request_comment = State()
