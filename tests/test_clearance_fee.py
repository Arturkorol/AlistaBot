import pytest

from bot_alista.tariff_engine import calc_clearance_fee_rub


@pytest.mark.parametrize("customs_value, expected", [
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
def test_clearance_fee_boundaries(customs_value, expected):
    assert calc_clearance_fee_rub(customs_value) == expected


def test_clearance_fee_requires_positive_value():
    with pytest.raises(ValueError):
        calc_clearance_fee_rub(-1)


def test_clearance_fee_returns_int():
    fee = calc_clearance_fee_rub(200_000)
    assert isinstance(fee, int)
