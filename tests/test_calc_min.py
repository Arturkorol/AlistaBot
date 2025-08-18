import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from calculator import (
    FL_STP_UNDER3_BY_VALUE_EUR,
    calculate_company,
    calculate_individual,
    pick_fl_under3_rule_by_value_eur,
)


@pytest.fixture(autouse=True)
def mock_rates(monkeypatch):
    rates = {"USD": 79.87, "EUR": 92.86, "RUB": 1.0}

    def fake_get_rate(code):
        return rates[code]

    monkeypatch.setattr("calculator._get_rate", fake_get_rate)


def test_fl_under3_by_value():
    res = calculate_individual(customs_value=20000, currency="USD", engine_cc=2500,
                               production_year=2022, fuel="Бензин")
    assert res["duty_rub"] > 600_000
    assert "clearance_fee_rub" in res


def test_fl_over3_specific():
    res = calculate_individual(customs_value=15000, currency="USD", engine_cc=3000,
                               production_year=2015, fuel="Бензин")
    assert res["duty_rub"] > 1_200_000


def test_ul_under3_15pct():
    res = calculate_company(customs_value=30000, currency="USD", engine_cc=2000,
                            production_year=2024, fuel="Бензин", hp=150)
    assert res["duty_rub"] > 300_000


def test_under3_table_source():
    rule = pick_fl_under3_rule_by_value_eur(8000)
    assert rule == FL_STP_UNDER3_BY_VALUE_EUR[0][1]
