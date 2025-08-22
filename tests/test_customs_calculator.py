import yaml
from pathlib import Path
from datetime import datetime
import sys
import copy

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services import CustomsCalculator

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
        car_type="Бензин",
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
        car_type="Бензин",
        power_hp=150,
    )
    # price 10_000 + customs payments 11_467 = 21_467
    assert etc["etc_eur"] == pytest.approx(21_467.0)


def test_configuration_values_drive_calculation():
    """Changing tariff values in config must affect the result."""
    year = datetime.now().year - 1
    tariffs = copy.deepcopy(SAMPLE_TARIFFS)
    tariffs["duty"]["under_3"]["per_cc"] = 0.01
    tariffs["duty"]["under_3"]["price_percent"] = 0.1
    tariffs["utilization"]["age_under_3"] = 100.0
    tariffs["vat"]["rate"] = 0.5
    tariffs["clearance_fee_rub"] = [[200000, 50]]

    calc = CustomsCalculator(eur_rate=1.0, tariffs=tariffs)
    res = calc.calculate_ctp(
        price_eur=1_000,
        engine_cc=1_000,
        year=year,
        car_type="Бензин",
    )

    # duty = max(1000*0.1, 1000*0.01) = 100
    # util = 100
    # vat = 0.5 * (1000 + 100 + 0 + 100) = 600
    # fee = 50
    expected_total = 100 + 100 + 600 + 50
    assert res["total_eur"] == pytest.approx(expected_total)
