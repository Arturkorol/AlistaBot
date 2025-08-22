import pathlib
import sys
import pytest

# Ensure repo root on path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tariff_engine import calc_import_duty_eur
import calculator
from calculator import calculate_individual


def test_calc_import_duty_minimum_applied():
    duty = calc_import_duty_eur(customs_value_eur=1000, engine_cc=2500)
    assert duty == pytest.approx(1100.0)


def test_calc_import_duty_with_zero_value_raises():
    with pytest.raises(ValueError):
        calc_import_duty_eur(customs_value_eur=0, engine_cc=2500)


def test_calculate_individual_unsupported_currency_fallback(monkeypatch):
    def mock_get_rate(for_date, code):
        raise RuntimeError("unsupported currency")
    monkeypatch.setattr(calculator, "get_cbr_rate", mock_get_rate)
    res = calculate_individual(
        customs_value=10000,
        currency="GBP",
        engine_cc=2000,
        production_year=2024,
        fuel="бензин",
    )
    assert res["currency_rate"] == 100.0
