import pytest
from datetime import date

tariff_engine = pytest.importorskip("tariff_engine")
calc_import_breakdown = tariff_engine.calc_import_breakdown
calc_breakdown_rules = tariff_engine.calc_breakdown_rules

from bot_alista.models import FuelType, PersonType, UsageType


def test_calc_import_breakdown_export_disabled_vehicle():
    result = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=True,
        is_export=True,
    )
    breakdown = result["breakdown"]
    assert breakdown["total_rub"] == 0.0
    assert breakdown["duty_eur"] == 0.0
    assert breakdown["excise_rub"] == 0.0
    assert breakdown["vat_rub"] == 0.0
    assert any("экспорт" in note.lower() for note in result["notes"])


def test_calc_breakdown_rules_individual_personal():
    result = calc_breakdown_rules(
        person_type=PersonType.INDIVIDUAL,
        usage_type=UsageType.PERSONAL,
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=None,
        production_year=2023,
        age_choice_over3=False,
        fuel_type=FuelType.GASOLINE,
        decl_date=date(2025, 1, 1),
    )
    b = result["breakdown"]
    assert b["excise_rub"] == 0.0
    assert b["vat_rub"] == 0.0
    expected_total = b["duty_rub"] + b["clearance_fee_rub"]
    assert b["total_rub"] == expected_total
    assert b["total_with_util_rub"] == b["total_rub"] + b["util_rub"]
    assert any("FL STP" in note for note in result["notes"])


def test_calc_breakdown_rules_company_commercial():
    result = calc_breakdown_rules(
        person_type=PersonType.COMPANY,
        usage_type=UsageType.COMMERCIAL,
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2023,
        age_choice_over3=False,
        fuel_type=FuelType.GASOLINE,
        decl_date=date(2025, 1, 1),
    )
    b = result["breakdown"]
    expected_total = (
        b["duty_rub"]
        + b["excise_rub"]
        + b["vat_rub"]
        + b["clearance_fee_rub"]
    )
    assert b["total_rub"] == expected_total
    assert b["total_with_util_rub"] == expected_total + b["util_rub"]
    assert any("UL by CSV" in note for note in result["notes"])


def test_calc_import_breakdown_validation_errors_negative():
    with pytest.raises(ValueError):
        calc_import_breakdown(
            customs_value_eur=-100,
            eur_rub_rate=100.0,
            engine_cc=2500,
            engine_hp=150,
            is_disabled_vehicle=False,
            is_export=False,
        )


def test_calc_import_breakdown_validation_errors_engine_range():
    with pytest.raises(ValueError):
        calc_import_breakdown(
            customs_value_eur=10000,
            eur_rub_rate=100.0,
            engine_cc=2000,
            engine_hp=150,
            is_disabled_vehicle=False,
            is_export=False,
        )
