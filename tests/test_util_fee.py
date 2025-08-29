from datetime import date
import copy
import pytest
from bot_alista.tariff.util_fee import calc_util_rub, load_util_config


def test_calc_util_rub_clamps_negative_diff():
    cfg = copy.deepcopy(load_util_config())
    res = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=1500,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=2.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=500000.0,
        actual_costs_rub=600000.0,
        config=cfg,
    )
    assert res == 3400.0


def test_calc_util_rub_requires_non_negative_costs():
    cfg = copy.deepcopy(load_util_config())
    with pytest.raises(ValueError):
        calc_util_rub(
            person_type="individual",
            usage="personal",
            engine_cc=1500,
            fuel="ice",
            vehicle_kind="passenger",
            age_years=2.0,
            date_decl=date(2025, 6, 1),
            avg_vehicle_cost_rub=-1.0,
            actual_costs_rub=1000.0,
            config=cfg,
        )
    with pytest.raises(ValueError):
        calc_util_rub(
            person_type="individual",
            usage="personal",
            engine_cc=1500,
            fuel="ice",
            vehicle_kind="passenger",
            age_years=2.0,
            date_decl=date(2025, 6, 1),
            avg_vehicle_cost_rub=1000.0,
            actual_costs_rub=None,
            config=cfg,
        )
