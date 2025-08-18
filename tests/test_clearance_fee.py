import pytest

from tariff_engine import calc_clearance_fee_rub
from calculator import CLEARANCE_FEE_TABLE, _pick_rate


@pytest.mark.parametrize("value, expected", [
    (200_000, 1_067),
    (200_001, 2_134),
    (450_000, 2_134),
    (450_001, 4_269),
    (1_200_000, 4_269),
    (1_200_001, 10_672),
    (2_500_000, 10_672),
    (2_500_001, 15_532),
    (5_000_000, 15_532),
    (5_000_001, 24_852),
    (7_000_000, 24_852),
    (7_000_001, 30_000),
])
def test_clearance_fee_boundaries(value, expected):
    assert calc_clearance_fee_rub(value) == expected
    assert _pick_rate(CLEARANCE_FEE_TABLE, value) == expected
