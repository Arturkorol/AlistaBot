import yaml
from pathlib import Path
from datetime import datetime

import pytest

from bot_alista.services.customs_calculator import CustomsCalculator

# Load sample tariff data
CONFIG = Path(__file__).resolve().parents[1] / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    SAMPLE_TARIFFS = yaml.safe_load(fh)


def test_calculate_ctp_returns_expected_total():
    """Verify customs tax payments using sample tariffs."""
    year = datetime.now().year - 1  # ensure vehicle is under 3 years old
    total = CustomsCalculator.calculate_ctp(
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type="Бензин",
        power_hp=150,
        eur_rate=1.0,
        tariffs=SAMPLE_TARIFFS,
    )
    assert total == pytest.approx(10_405.0)


def test_calculate_etc_includes_vehicle_price():
    """ETC should equal purchase price plus customs payments."""
    year = datetime.now().year - 1
    etc = CustomsCalculator.calculate_etc(
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type="Бензин",
        power_hp=150,
        eur_rate=1.0,
        tariffs=SAMPLE_TARIFFS,
    )
    # price 10_000 + customs payments 10_405 = 20_405
    assert etc == pytest.approx(20_405.0)
