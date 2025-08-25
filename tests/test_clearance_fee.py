from bot_alista.clearance_fee import calc_clearance_fee_rub
import pytest


def test_clearance_fee_returns_int():
    assert isinstance(calc_clearance_fee_rub(150000), int)
    assert calc_clearance_fee_rub(150000) == 1067


def test_clearance_fee_negative_value():
    with pytest.raises(ValueError):
        calc_clearance_fee_rub(-1)
