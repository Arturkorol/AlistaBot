import os
import sys
from datetime import date

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from bot_alista.tariff_engine import (
    calc_breakdown_with_mode,
    calc_import_duty_eur,
    pick_fl_under3_rule_by_value_eur,
    _get_rate,
)


@pytest.fixture(autouse=True)
def mock_rates(monkeypatch):
    rates = {"USD": 79.87, "EUR": 92.86}

    def fake_cached_rate(for_date, code):
        return rates[code]

    monkeypatch.setattr("bot_alista.tariff_engine.get_cached_rate", fake_cached_rate)


def test_fl_under3_by_value():
    usd_rate = _get_rate("USD")
    eur_rate = _get_rate("EUR")
    customs_value_eur = 20000 * usd_rate / eur_rate
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=customs_value_eur,
        eur_rub_rate=eur_rate,
        engine_cc=2500,
        engine_hp=150,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
    )
    assert res["breakdown"]["duty_rub"] > 600_000
    assert "clearance_fee_rub" in res["breakdown"]


def test_fl_over3_specific():
    usd_rate = _get_rate("USD")
    eur_rate = _get_rate("EUR")
    customs_value_eur = 15000 * usd_rate / eur_rate
    age_years = date.today().year - 2015
    res = calc_breakdown_with_mode(
        person_type="individual",
        usage_type="personal",
        customs_value_eur=customs_value_eur,
        eur_rub_rate=eur_rate,
        engine_cc=3000,
        engine_hp=200,
        age_years=age_years,
        is_disabled_vehicle=False,
        is_export=False,
    )
    assert res["breakdown"]["duty_rub"] > 1_200_000


def test_corp_duty_calculation():
    usd_rate = _get_rate("USD")
    eur_rate = _get_rate("EUR")
    customs_value_eur = 30000 * usd_rate / eur_rate
    res = calc_breakdown_with_mode(
        person_type="company",
        usage_type="commercial",
        customs_value_eur=customs_value_eur,
        eur_rub_rate=eur_rate,
        engine_cc=2500,
        engine_hp=150,
        age_years=1.0,
        is_disabled_vehicle=False,
        is_export=False,
    )
    assert res["breakdown"]["duty_rub"] > 300_000
    assert res["breakdown"]["vat_rub"] > 0


def test_import_duty_switch():
    assert calc_import_duty_eur(5000, 3000) == 1320.0
    assert calc_import_duty_eur(30000, 2500) == 6000.0


def test_pick_fl_under3_rule_negative():
    with pytest.raises(ValueError):
        pick_fl_under3_rule_by_value_eur(-100)
