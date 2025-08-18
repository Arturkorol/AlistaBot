import math
from datetime import date

import pytest
from bot_alista.tariff_engine import calc_breakdown_with_mode


def test_fl_under3_by_value():
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=20_000,
        eur_rub_rate=92.86,
        engine_cc=2500,
        engine_hp=150,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
    )
    b = res["breakdown"]
    assert b["duty_rub"] > 600_000
    assert "clearance_fee_rub" in b


def test_fl_over3_specific():
    age = float(date.today().year - 2015)
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=15_000,
        eur_rub_rate=92.86,
        engine_cc=3000,
        engine_hp=200,
        age_years=age,
        is_disabled_vehicle=False,
        is_export=False,
    )
    assert res["breakdown"]["duty_rub"] > 1_200_000


def test_ul_under3_20pct():
    res = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=30_000,
        eur_rub_rate=92.86,
        engine_cc=2500,
        engine_hp=150,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
    )
    assert res["breakdown"]["duty_rub"] > 300_000


def test_ul_electric_excise_zero():
    res = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=30_000,
        eur_rub_rate=92.86,
        engine_cc=2300,
        engine_hp=1,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
    )
    b = res["breakdown"]
    assert b["excise_rub"] == 0
    expected_vat = (b["customs_value_rub"] + b["duty_rub"]) * 0.20
    assert math.isclose(b["vat_rub"], expected_vat, rel_tol=1e-6)

