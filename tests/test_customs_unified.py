from bot_alista.tariff import CustomsCalculator
from bot_alista.clearance_fee import calc_clearance_fee_rub


def test_calculate_ctp():
    calc = CustomsCalculator("config.yaml")
    calc.set_vehicle(
        age="1-3",
        engine_capacity=2500,
        engine_type="gasoline",
        power=150,
        price=20000,
        currency="USD",
        owner_type="individual",
    )
    res = calc.calculate_ctp()
    assert res == {
        "price_rub": 2_000_000.0,
        "duty_rub": 400_000.0,
        "excise_rub": 8_700.0,
        "vat_rub": 481_740.0,
        "clearance_rub": 11_746,
        "util_rub": 24_000.0,
        "recycling_rub": 0.0,
        "total_rub": 926_186.0,
    }


def test_calculate_etc():
    calc = CustomsCalculator("config.yaml")
    calc.set_vehicle(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        currency="USD",
        owner_type="individual",
    )
    res = calc.calculate_etc()
    assert res == {
        "price_rub": 1_000_000.0,
        "duty_rub": 1_056_000.0,
        "excise_rub": 0.0,
        "vat_rub": 0.0,
        "clearance_rub": 3_100,
        "util_rub": 20_000.0,
        "recycling_rub": 5_200.0,
        "total_rub": 1_084_300.0,
    }


def test_clearance_fee_helper():
    ranges = [(500, 10), (float("inf"), 20)]
    assert calc_clearance_fee_rub(100, ranges) == 10
