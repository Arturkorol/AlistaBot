import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services import customs


VEHICLE = dict(
    age="5-7",
    engine_capacity=2000,
    engine_type="gasoline",
    power=150,
    price=10000,
    owner_type="individual",
    currency="USD",
)

def test_get_calculator_returns_customs_calculator():
    calc = customs.get_calculator()
    assert isinstance(calc, customs.CustomsCalculator)

def test_calculate_wrappers_match_class():
    ctp = customs.calculate_ctp(**VEHICLE)
    etc = customs.calculate_etc(**VEHICLE)

    calc = customs.CustomsCalculator()
    calc.set_vehicle_details(**VEHICLE)
    expected_ctp = calc.calculate_ctp()
    calc.set_vehicle_details(**VEHICLE)
    expected_etc = calc.calculate_etc()

    assert ctp == expected_ctp
    assert etc == expected_etc
