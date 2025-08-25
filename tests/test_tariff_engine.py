import pytest
from datetime import date
import pytest

tariff_engine = pytest.importorskip("tariff_engine")
calc_import_breakdown = tariff_engine.calc_import_breakdown
calc_breakdown_rules = tariff_engine.calc_breakdown_rules
calc_breakdown_with_mode = tariff_engine.calc_breakdown_with_mode


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
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=None,
        production_year=2023,
        age_choice_over3=False,
        fuel_type="Бензин",
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
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2023,
        age_choice_over3=False,
        fuel_type="Бензин",
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


def test_util_fee_varies_with_age():
    older = calc_breakdown_rules(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=None,
        production_year=2021,
        age_choice_over3=True,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    newer = calc_breakdown_rules(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=None,
        production_year=2022,
        age_choice_over3=True,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    util_old = older["breakdown"]["util_rub"]
    util_new = newer["breakdown"]["util_rub"]
    assert util_old > util_new


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


def test_decimal_rounding():
    assert tariff_engine.eur_to_rub(0.005, 1) == 0.01


def test_personal_duty_loader():
    from bot_alista.tariff.personal_rates import calc_individual_personal_duty_eur

    assert calc_individual_personal_duty_eur(2500, 4.0) == 7500.0


def test_preferential_country_reduces_duty():
    base = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=False,
        is_export=False,
    )
    pref = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=False,
        is_export=False,
        country_origin="Belarus",
    )
    assert pref["breakdown"]["duty_eur"] < base["breakdown"]["duty_eur"]
    assert any("преференция" in n.lower() for n in pref["notes"])


def test_calc_breakdown_with_mode_uses_fuel_and_date():
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    expected = calc_breakdown_rules(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2024,
        age_choice_over3=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    assert res["breakdown"]["util_rub"] == expected["breakdown"]["util_rub"]


def test_rule_fallback_note(monkeypatch):
    calls = {"n": 0}

    def fake_calc_fl_stp(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("boom")
        return {"duty_eur": 1.0, "duty_rub": 1.0, "excise_rub": 0.0, "vat_rub": 0.0}

    from bot_alista.tariff import engine as engine_mod

    monkeypatch.setattr(engine_mod, "calc_fl_stp", fake_calc_fl_stp)
    res = engine_mod.calc_breakdown_rules(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=100,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=None,
        production_year=2024,
        age_choice_over3=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    assert any("fallback" in n.lower() for n in res["notes"])
