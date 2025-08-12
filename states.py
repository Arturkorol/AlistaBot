from aiogram.fsm.state import State, StatesGroup

# Состояния расчёта растаможки
class CalculationStates(StatesGroup):
    calc_type = State()
    calc_price = State()
    calc_engine = State()
    calc_power = State()
    calc_year = State()
    calc_weight = State()
    manual_eur_rate = State()
    email_confirm = State()
    email_request = State()

# Состояния подачи заявки
class RequestStates(StatesGroup):
    request_name = State()
    request_car = State()
    request_contact = State()
    request_price = State()
    request_comment = State()
