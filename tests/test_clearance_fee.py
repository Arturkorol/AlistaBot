import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tariff_engine import (
    calc_clearance_fee_rub,
    CLEARANCE_FEE_TABLE,
    _pick_rate,
)


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
    assert _pick_rate(CLEARANCE_FEE_TABLE, value) == expected
