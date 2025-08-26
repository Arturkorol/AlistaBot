import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator, WrongParamException

CONFIG_PATH = ROOT / "external/tks_api_official/config.yaml"


def _make_calc():
    return CustomsCalculator(str(CONFIG_PATH))


@pytest.mark.parametrize("age", ["1-3", "5-7"])
def test_calculate_etc_and_ctp(age):
    calc = _make_calc()
    calc.set_vehicle_details(
        age=age,
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        owner_type="individual",
        currency="USD",
    )
    calc.convert_to_local_currency = lambda amount, currency='EUR': float(amount) * 100
    etc = calc.calculate_etc()
    ctp = calc.calculate_ctp()
    assert etc["Mode"] == "ETC"
    assert ctp["Mode"] == "CTP"
    assert etc["Total Pay (RUB)"] > 0
    assert ctp["Total Pay (RUB)"] > 0


def test_calculate_auto_returns_one_of_methods():
    calc = _make_calc()
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        owner_type="individual",
        currency="USD",
    )
    calc.convert_to_local_currency = lambda amount, currency='EUR': float(amount) * 100
    auto = calc.calculate_auto()
    assert auto["Mode"] in {"ETC", "CTP"}
    assert auto["Total Pay (RUB)"] > 0


def test_convert_to_local_currency_error():
    calc = _make_calc()

    def bad_convert(amount, currency, target):
        raise ValueError("fail")

    calc.converter.convert = bad_convert
    with pytest.raises(WrongParamException):
        calc.convert_to_local_currency(1, "EUR")


def test_calculate_methods_propagate_conversion_error():
    calc = _make_calc()
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        owner_type="individual",
        currency="USD",
    )

    def bad(*args, **kwargs):
        raise WrongParamException("boom")

    calc.convert_to_local_currency = bad

    with pytest.raises(WrongParamException) as exc:
        calc.calculate_etc()
    assert "ETC" in str(exc.value)

    with pytest.raises(WrongParamException) as exc:
        calc.calculate_ctp()
    assert "CTP" in str(exc.value)

