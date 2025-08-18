import os
import sys
from datetime import date

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tariff_engine import (
    calc_breakdown_rules,
    calc_breakdown_with_mode,
    calc_clearance_fee_rub,
    eur_to_rub,
)
from bot_alista.rules.loader import load_rules
from bot_alista.rules.engine import calc_ul
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG

EUR_RUB_RATE = 100.0
CUSTOMS_VALUE_EUR = 10_000.0
DECL_DATE = date(2024, 12, 31)
CUSTOMS_VALUE_RUB = CUSTOMS_VALUE_EUR * EUR_RUB_RATE
CLEARANCE_FEE = calc_clearance_fee_rub(CUSTOMS_VALUE_RUB)


@pytest.mark.parametrize(
    "case",
    [
        # FL ≤3y, 1801–2300 cc (upper boundary 2300)
        {
            "person_type": "individual",
            "usage_type": "personal",
            "engine_cc": 2300,
            "engine_hp": 150,
            "production_year": 2022,  # age 2y
            "age_choice_over3": False,
            "per_cc": 6.2,
            "util_age": 2.0,
        },
        # FL ≤3y, 2301–3000 cc (lower boundary 2301)
        {
            "person_type": "individual",
            "usage_type": "personal",
            "engine_cc": 2301,
            "engine_hp": 150,
            "production_year": 2022,  # age 2y
            "age_choice_over3": False,
            "per_cc": 5.5,
            "util_age": 2.0,
        },
        # FL 3–5y, 2301–3000 cc, age boundary 3y
        {
            "person_type": "individual",
            "usage_type": "personal",
            "engine_cc": 2301,
            "engine_hp": 150,
            "production_year": 2021,  # age 3y
            "age_choice_over3": True,
            "per_cc": 3.0,
            "util_age": 4.0,
        },
        # FL >7y, 3001–10000 cc (lower boundary 3001)
        {
            "person_type": "individual",
            "usage_type": "personal",
            "engine_cc": 3001,
            "engine_hp": 150,
            "production_year": 2016,  # age 8y
            "age_choice_over3": True,
            "per_cc": 5.7,
            "util_age": 4.0,
        },
        # UL 3–7y, 2301–3000 cc (lower boundary 2301)
        {
            "person_type": "company",
            "usage_type": "commercial",
            "engine_cc": 2301,
            "engine_hp": 150,
            "production_year": 2020,  # age 4y
            "age_choice_over3": True,
            "duty_pct": 20.0,
            "min_eur_cc": 0.44,
            "vat_pct": 20.0,
            "util_age": 4.0,
            "expected_excise": 0.0,
        },
    ],
)
def test_csv_tariff_brackets(case):
    if case["person_type"] == "company":
        core = calc_ul(
            rules=load_rules(),
            customs_value_eur=CUSTOMS_VALUE_EUR,
            eur_rub_rate=EUR_RUB_RATE,
            engine_cc=case["engine_cc"],
            engine_hp=case["engine_hp"],
            segment="Легковой",
            category="M1",
            fuel="Бензин",
            age_bucket="3–7",
        )
        duty_rub = core["duty_rub"]
        vat_rub = core["vat_rub"]
        excise_rub = core["excise_rub"]
        fee_rub = CLEARANCE_FEE
        util_rub = calc_util_rub(
            person_type="company",
            usage="commercial",
            engine_cc=case["engine_cc"],
            fuel="ice",
            vehicle_kind="passenger",
            age_years=case["util_age"],
            date_decl=DECL_DATE,
            avg_vehicle_cost_rub=None,
            actual_costs_rub=None,
            config=UTIL_CONFIG,
        )
    else:
        res = calc_breakdown_rules(
            person_type=case["person_type"],
            usage_type=case["usage_type"],
            customs_value_eur=CUSTOMS_VALUE_EUR,
            eur_rub_rate=EUR_RUB_RATE,
            engine_cc=case["engine_cc"],
            engine_hp=case["engine_hp"],
            production_year=case["production_year"],
            age_choice_over3=case["age_choice_over3"],
            fuel_type="Бензин",
            decl_date=DECL_DATE,
        )

        breakdown = res["breakdown"]
        duty_rub = breakdown["duty_rub"]
        vat_rub = breakdown["vat_rub"]
        excise_rub = breakdown["excise_rub"]
        fee_rub = breakdown["clearance_fee_rub"]
        util_rub = breakdown["util_rub"]

    customs_value_rub = CUSTOMS_VALUE_EUR * EUR_RUB_RATE

    if "per_cc" in case:
        expected_duty_eur = case["engine_cc"] * case["per_cc"]
        expected_duty_rub = eur_to_rub(expected_duty_eur, EUR_RUB_RATE)
        expected_excise = 0.0
        expected_vat = 0.0
    else:
        ad_valorem = CUSTOMS_VALUE_EUR * case["duty_pct"] / 100.0
        min_eur = case["engine_cc"] * case["min_eur_cc"]
        expected_duty_eur = max(ad_valorem, min_eur)
        expected_duty_rub = eur_to_rub(expected_duty_eur, EUR_RUB_RATE)
        expected_excise = case.get("expected_excise", 0.0)
        expected_vat = round((customs_value_rub + expected_duty_rub + expected_excise) * case["vat_pct"] / 100.0, 2)

    expected_fee = CLEARANCE_FEE
    expected_util = calc_util_rub(
        person_type=case["person_type"],
        usage=case["usage_type"],
        engine_cc=case["engine_cc"],
        fuel="ice",
        vehicle_kind="passenger",
        age_years=case["util_age"],
        date_decl=DECL_DATE,
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=UTIL_CONFIG,
    )

    assert duty_rub == expected_duty_rub
    assert excise_rub == expected_excise
    assert vat_rub == expected_vat
    assert fee_rub == expected_fee
    assert util_rub == expected_util


@pytest.mark.parametrize(
    "customs_value, expected_fee",
    [
        (200_000, 1_067.0),
        (200_001, 2_134.0),
        (450_000, 2_134.0),
        (450_001, 4_269.0),
        (1_200_000, 4_269.0),
        (1_200_001, 11_746.0),
        (3_000_000, 11_746.0),
        (3_000_001, 16_524.0),
        (5_000_000, 16_524.0),
        (5_000_001, 20_000.0),
        (7_000_000, 20_000.0),
        (7_000_001, 30_000.0),
    ],
)
def test_clearance_fee_brackets(customs_value, expected_fee):
    assert calc_clearance_fee_rub(customs_value) == expected_fee


def test_export_breakdown_zero():
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=CUSTOMS_VALUE_EUR,
        eur_rub_rate=EUR_RUB_RATE,
        engine_cc=2500,
        engine_hp=150,
        age_years=2.0,
        is_disabled_vehicle=False,
        is_export=True,
    )
    b = res["breakdown"]
    assert b["duty_rub"] == 0.0
    assert b["vat_rub"] == 0.0
    assert b["excise_rub"] == 0.0
    assert b.get("util_rub", 0.0) == 0.0
    assert b.get("clearance_fee_rub", 0.0) == 0.0


def test_electric_vehicle_not_supported():
    with pytest.raises(ValueError):
        calc_breakdown_rules(
            person_type="individual",
            usage_type="personal",
            customs_value_eur=CUSTOMS_VALUE_EUR,
            eur_rub_rate=EUR_RUB_RATE,
            engine_cc=2300,
            engine_hp=150,
            production_year=2022,
            age_choice_over3=False,
            fuel_type="Электро",
            decl_date=DECL_DATE,
        )
