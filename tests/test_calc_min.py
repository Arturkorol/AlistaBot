import os
import sys

import math
from datetime import date
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from calculator import (
    calculate_individual,
    calculate_company,
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
                               production_year=date.today().year - 1, fuel="Бензин")
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


def test_ul_3_5_petrol_brackets():
    res_small = calculate_company(customs_value=10000, currency="USD", engine_cc=1200,
                                  production_year=2022, fuel="Бензин", hp=100)
    res_large = calculate_company(customs_value=10000, currency="USD", engine_cc=2600,
                                  production_year=2022, fuel="Бензин", hp=100)
    eur_rate = 92.86
    assert math.isclose(res_small["duty_rub"], 1200 * 1.7 * eur_rate, rel_tol=1e-6)
    assert math.isclose(res_large["duty_rub"], 2600 * 3.0 * eur_rate, rel_tol=1e-6)


def test_ul_5_7_diesel_brackets():
    res_small = calculate_company(customs_value=10000, currency="USD", engine_cc=1200,
                                  production_year=2019, fuel="Дизель", hp=100)
    res_large = calculate_company(customs_value=10000, currency="USD", engine_cc=2600,
                                  production_year=2019, fuel="Дизель", hp=100)
    eur_rate = 92.86
    assert math.isclose(res_small["duty_rub"], 1200 * 3.2 * eur_rate, rel_tol=1e-6)
    assert math.isclose(res_large["duty_rub"], 2600 * 5.0 * eur_rate, rel_tol=1e-6)


def test_pick_fl_under3_rule_negative():
    with pytest.raises(ValueError):
        pick_fl_under3_rule_by_value_eur(-100)
