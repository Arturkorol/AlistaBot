from __future__ import annotations

"""Example script demonstrating util_fee calculations."""

from datetime import date
import copy

from bot_alista.tariff.util_fee import calc_util_rub, load_util_config


if __name__ == "__main__":
    # Example 1: individual, personal use
    fee1 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=1800,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=2.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(load_util_config()),
    )
    print(f"Example 1: {fee1} RUB")

    # Example 2: company, commercial EV
    fee2 = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=0,
        fuel="ev",
        vehicle_kind="commercial",
        age_years=1.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(load_util_config()),
    )
    print(f"Example 2: {fee2} RUB")

    # Example 3: post-2025 with cost difference and not-in-list multiplier
    config3 = copy.deepcopy(load_util_config())
    config3["not_in_list"] = True
    fee3 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=2500,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=4.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=800000.0,
        actual_costs_rub=600000.0,
        config=config3,
    )
    print(f"Example 3: {fee3} RUB")
