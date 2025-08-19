import pytest
from datetime import date

from bot_alista.tariff_engine import calc_clearance_fee_rub
import calculator
from calculator import calculate_individual


@pytest.mark.parametrize("value, expected", [
    (200_000, 1_067),
    (200_001, 2_134),
    (450_000, 2_134),
    (450_001, 4_269),
    (1_200_000, 4_269),
    (1_200_001, 11_746),
    (3_000_000, 11_746),
    (3_000_001, 16_524),
    (5_000_000, 16_524),
    (5_000_001, 20_000),
    (7_000_000, 20_000),
    (7_000_001, 30_000),
])
def test_clearance_fee_boundaries(value, expected):
    assert calc_clearance_fee_rub(value) == expected


def test_calculator_uses_clearance_fee_function(monkeypatch):
    """calculator module should delegate clearance fee computation to tariff_engine."""
    monkeypatch.setattr(calculator, "get_cached_rate", lambda *args, **kwargs: 100.0)
    value = 450_001
    res = calculate_individual(
        customs_value=value,
        currency="RUB",
        engine_cc=1500,
        production_year=date.today().year,
        fuel="Бензин",
    )
    assert res["clearance_fee_rub"] == calc_clearance_fee_rub(value)
