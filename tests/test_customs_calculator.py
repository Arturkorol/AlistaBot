import yaml
from pathlib import Path
from datetime import datetime
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator
from bot_alista.models import FuelType, WrongParamException

# Load sample tariff data
CONFIG = Path(__file__).resolve().parents[1] / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    SAMPLE_TARIFFS = yaml.safe_load(fh)


def test_calculate_ctp_returns_expected_total():
    """Verify customs tax payments using sample tariffs."""
    year = datetime.now().year - 1  # ensure vehicle is under 3 years old
    calc = CustomsCalculator(eur_rate=1.0, tariffs=SAMPLE_TARIFFS)
    res = calc.calculate_ctp(
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type=FuelType.GASOLINE,
        power_hp=150,
    )
    assert res["total_eur"] == pytest.approx(11_467.0)


def test_calculate_etc_includes_vehicle_price():
    """ETC should equal purchase price plus customs payments."""
    year = datetime.now().year - 1
    calc = CustomsCalculator(eur_rate=1.0, tariffs=SAMPLE_TARIFFS)
    etc = calc.calculate_etc(
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type=FuelType.GASOLINE,
        power_hp=150,
    )
    # price 10_000 + customs payments 11_467 = 21_467
    assert etc["etc_eur"] == pytest.approx(21_467.0)


def test_calculate_ctp_invalid_fuel_type():
    year = datetime.now().year - 1
    calc = CustomsCalculator(eur_rate=1.0, tariffs=SAMPLE_TARIFFS)
    with pytest.raises(WrongParamException):
        calc.calculate_ctp(
            price_eur=10_000,
            engine_cc=2_000,
            year=year,
            car_type="water",
            power_hp=150,
        )
