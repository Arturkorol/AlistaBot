import pytest
from datetime import date

from bot_alista.tariff import (
    calc_breakdown_rules,
    calc_breakdown_with_mode,
    calc_import_breakdown,
    eur_to_rub,
)
from bot_alista.clearance_fee import calc_clearance_fee_rub
from bot_alista.tariff.util_fee import calc_util_rub, load_util_config
from bot_alista.rules.loader import RuleRow
from bot_alista.rules.engine import calc_ul


def test_calc_import_breakdown_export_disabled_vehicle():
    result = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=True,
        is_export=True,
        age_years=0.0,
    )
    breakdown = result["breakdown"]
    assert breakdown["total_rub"] == 0.0
    assert breakdown["duty_eur"] == 0.0
    assert breakdown["excise_rub"] == 0.0
    assert breakdown["vat_rub"] == 0.0
    assert breakdown["clearance_fee_rub"] == 0.0
    assert breakdown["util_rub"] == 0.0
    assert any("экспорт" in note.lower() for note in result["notes"])


def test_calc_import_breakdown_includes_fees(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    fixed_date = date(2025, 1, 1)
    monkeypatch.setattr(engine_mod, "date", type("d", (), {"today": staticmethod(lambda: fixed_date)}))

    res = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=False,
        is_export=False,
        age_years=4.0,
    )
    b = res["breakdown"]
    customs_value_rub = eur_to_rub(10000, 100.0)
    fee_expected = calc_clearance_fee_rub(customs_value_rub)
    util_expected = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=2500,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=4.0,
        date_decl=fixed_date,
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=load_util_config(),
    )
    total_expected = b["duty_rub"] + b["excise_rub"] + b["vat_rub"] + fee_expected + util_expected
    assert b["clearance_fee_rub"] == fee_expected
    assert b["util_rub"] == util_expected
    assert b["total_rub"] == total_expected


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


def test_calc_breakdown_rules_company_commercial(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    orig_calc_ul = engine_mod.calc_ul

    def wrapped_calc_ul(*args, **kwargs):
        kwargs.setdefault("vat_override_pct", 20.0)
        return orig_calc_ul(*args, **kwargs)

    monkeypatch.setattr(engine_mod, "calc_ul", wrapped_calc_ul)

    result = calc_breakdown_rules(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2021,
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


def test_calc_breakdown_rules_requires_engine_cc():
    with pytest.raises(ValueError):
        calc_breakdown_rules(
            person_type="individual",
            usage_type="personal",
            customs_value_eur=10000,
            eur_rub_rate=100.0,
            engine_cc=None,
            engine_hp=None,
            production_year=2023,
            age_choice_over3=False,
            fuel_type="Бензин",
            decl_date=date(2025, 1, 1),
        )


def test_calc_breakdown_rules_requires_engine_hp_for_ul():
    with pytest.raises(ValueError):
        calc_breakdown_rules(
            person_type="company",
            usage_type="commercial",
            customs_value_eur=10000,
            eur_rub_rate=100.0,
            engine_cc=2500,
            engine_hp=None,
            production_year=2023,
            age_choice_over3=False,
            fuel_type="Бензин",
            decl_date=date(2025, 1, 1),
        )


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


def test_calc_ul_requires_vat():
    rule = RuleRow(
        segment="S",
        category="C",
        fuel="F",
        age_bucket="A",
        cc_from=None,
        cc_to=None,
        hp_from=None,
        hp_to=None,
        duty_type="Адвалор",
        duty_pct=10.0,
        min_eur_cc=None,
        spec_eur_cc=None,
        stp_pct=None,
        stp_min_eur_cc=None,
        vat_pct=None,
        excise_rub_hp=0.0,
    )
    with pytest.raises(ValueError):
        calc_ul(
            rules=[rule],
            customs_value_eur=1000,
            eur_rub_rate=100.0,
            engine_cc=2000,
            engine_hp=100,
            segment="S",
            category="C",
            fuel="F",
            age_bucket="A",
        )


def test_calc_ul_vat_override():
    rule = RuleRow(
        segment="S",
        category="C",
        fuel="F",
        age_bucket="A",
        cc_from=None,
        cc_to=None,
        hp_from=None,
        hp_to=None,
        duty_type="Адвалор",
        duty_pct=10.0,
        min_eur_cc=None,
        spec_eur_cc=None,
        stp_pct=None,
        stp_min_eur_cc=None,
        vat_pct=None,
        excise_rub_hp=0.0,
    )
    res = calc_ul(
        rules=[rule],
        customs_value_eur=1000,
        eur_rub_rate=100.0,
        engine_cc=2000,
        engine_hp=100,
        segment="S",
        category="C",
        fuel="F",
        age_bucket="A",
        vat_override_pct=18.0,
    )
    assert res["vat_rub"] == 19800.0


def test_calc_import_breakdown_validation_errors_negative():
    with pytest.raises(ValueError):
        calc_import_breakdown(
            customs_value_eur=-100,
            eur_rub_rate=100.0,
            engine_cc=2500,
            engine_hp=150,
            is_disabled_vehicle=False,
            is_export=False,
            age_years=0.0,
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
            age_years=0.0,
        )


def test_decimal_rounding():
    assert eur_to_rub(0.005, 1) == 0.01


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
        age_years=0.0,
        avg_vehicle_cost_rub=0.0,
        actual_costs_rub=0.0,
    )
    pref = calc_import_breakdown(
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        is_disabled_vehicle=False,
        is_export=False,
        age_years=0.0,
        avg_vehicle_cost_rub=0.0,
        actual_costs_rub=0.0,
        country_origin="Belarus",
    )
    assert pref["breakdown"]["duty_eur"] < base["breakdown"]["duty_eur"]
    assert any("преференция" in n.lower() for n in pref["notes"])


def test_calc_breakdown_rules_preferential_country(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    orig_calc_ul = engine_mod.calc_ul

    def wrapped_calc_ul(*args, **kwargs):
        kwargs.setdefault("vat_override_pct", 20.0)
        return orig_calc_ul(*args, **kwargs)

    monkeypatch.setattr(engine_mod, "calc_ul", wrapped_calc_ul)
    monkeypatch.setattr(engine_mod, "candidate_ul_labels", lambda *a, **k: ["3–7"])

    base = calc_breakdown_rules(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2021,
        age_choice_over3=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    pref = calc_breakdown_rules(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2021,
        age_choice_over3=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
        country_origin="Belarus",
    )
    assert pref["breakdown"]["duty_rub"] < base["breakdown"]["duty_rub"]
    assert any("преференция" in n.lower() for n in pref["notes"])


def test_calc_breakdown_with_mode_preferential_country(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    orig_calc_ul = engine_mod.calc_ul

    def wrapped_calc_ul(*args, **kwargs):
        kwargs.setdefault("vat_override_pct", 20.0)
        return orig_calc_ul(*args, **kwargs)

    monkeypatch.setattr(engine_mod, "calc_ul", wrapped_calc_ul)
    monkeypatch.setattr(engine_mod, "candidate_ul_labels", lambda *a, **k: ["3–7"])

    base = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        age_years=4.0,
        is_disabled_vehicle=False,
        is_export=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    pref = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        age_years=4.0,
        is_disabled_vehicle=False,
        is_export=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
        country_origin="Belarus",
    )
    assert pref["breakdown"]["duty_rub"] < base["breakdown"]["duty_rub"]
    assert any("преференция" in n.lower() for n in pref.get("notes", []))


def test_util_fee_uses_cost_params(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    def fake_util(*, avg_vehicle_cost_rub, actual_costs_rub, **kwargs):
        return float(avg_vehicle_cost_rub or 0) + float(actual_costs_rub or 0)

    monkeypatch.setattr(engine_mod, "calc_util_rub", fake_util)

    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        age_years=4.0,
        is_disabled_vehicle=False,
        is_export=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
        avg_vehicle_cost_rub=100.0,
        actual_costs_rub=200.0,
    )

    assert res["breakdown"]["util_rub"] == 300.0


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


def test_calc_breakdown_with_mode_fractional_age(monkeypatch):
    import bot_alista.tariff.engine as engine_mod

    orig_calc_ul = engine_mod.calc_ul

    def wrapped_calc_ul(*args, **kwargs):
        kwargs.setdefault("vat_override_pct", 20.0)
        return orig_calc_ul(*args, **kwargs)

    monkeypatch.setattr(engine_mod, "calc_ul", wrapped_calc_ul)

    res = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        age_years=3.2,
        is_disabled_vehicle=False,
        is_export=False,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    expected = calc_breakdown_rules(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=10000,
        eur_rub_rate=100.0,
        engine_cc=2500,
        engine_hp=150,
        production_year=2021,
        age_choice_over3=True,
        fuel_type="Бензин",
        decl_date=date(2025, 1, 1),
    )
    assert res["breakdown"]["util_rub"] == expected["breakdown"]["util_rub"]
    assert any("age_bucket=3" in note or "age_bucket=3–5" in note for note in res["notes"])


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
