from datetime import date
from copy import deepcopy

from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG


def test_util_fee_individual_personal():
    config = deepcopy(UTIL_CONFIG)
    fee = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=1800,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=2.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=config,
    )
    assert fee == 3400.0


def test_util_fee_company_commercial():
    config = deepcopy(UTIL_CONFIG)
    fee = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=2000,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=1.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=config,
    )
    assert fee == 445000.0

