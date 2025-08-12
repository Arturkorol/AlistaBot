from aiogram.fsm.state import State, StatesGroup


class CalculationStates(StatesGroup):
    vehicle_type = State()
    fuel_type = State()
    engine_cc = State()
    engine_hp = State()
    age_years = State()
    person_type = State()
    usage_type = State()
    country_origin = State()
    decl_date = State()
    currency_code = State()
    customs_value_amount = State()
    eur_rate = State()
    avg_vehicle_cost_rub = State()
    actual_costs_rub = State()
    confirm = State()
