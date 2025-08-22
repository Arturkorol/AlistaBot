import sys
from pathlib import Path
from datetime import date

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import calculator
from tariff_engine import calc_clearance_fee_rub as engine_fee
from bot_alista.tariff.clearance_fee import calc_clearance_fee_rub


@pytest.mark.parametrize("value", [100_000, 200_000, 200_001, 450_000, 1_200_000, 3_500_000, 6_500_000, 8_000_000])
def test_clearance_fee_consistency(monkeypatch, value):
    # Consistency between shared module and tariff_engine
    assert calc_clearance_fee_rub(value) == engine_fee(value)

    # Stub out external rate fetching
    monkeypatch.setattr(calculator, "_get_rate", lambda code: 1.0)

    # Calculator should produce the same fee
    result = calculator.calculate_company(
        customs_value=value,
        currency="RUB",
        engine_cc=2500,
        production_year=date.today().year,
        fuel="бензин",
        hp=150,
    )
    assert result["clearance_fee_rub"] == calc_clearance_fee_rub(value)
