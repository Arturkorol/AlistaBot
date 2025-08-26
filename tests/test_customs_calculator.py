import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator
import yaml


def _make_calc(config_path):
    return CustomsCalculator(str(config_path))


import pytest


@pytest.fixture
def config_file(tmp_path):
    data = {
        'tariffs': {
            'age_groups': {
                'overrides': {
                    '5-7': {
                        'gasoline': {'rate_per_cc': 1.0}
                    }
                }
            },
            'base_clearance_fee': 1000,
            'base_util_fee': 500,
            'ctp_util_coeff_base': 1.0,
            'recycling_factors': {
                'default': {'gasoline': 1.0},
                'adjustments': {}
            },
            'excise_rates': {'gasoline': 0.0}
        }
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(data))
    return path


def test_calculate_etc_and_ctp(config_file):
    calc = _make_calc(config_file)
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
    etc = calc.calculate_etc()
    ctp = calc.calculate_ctp()
    assert etc["Mode"] == "ETC"
    assert ctp["Mode"] == "CTP"
    assert etc["Total Pay (RUB)"] > 0
    assert ctp["Total Pay (RUB)"] > 0


def test_calculate_auto_returns_one_of_methods(config_file):
    calc = _make_calc(config_file)
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
