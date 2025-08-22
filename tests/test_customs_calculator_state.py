from datetime import datetime
from pathlib import Path
import yaml
import pytest
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator
from bot_alista.models import FuelType

CONFIG = Path(__file__).resolve().parents[1] / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    SAMPLE_TARIFFS = yaml.safe_load(fh)


def test_state_reset_between_calls():
    year = datetime.now().year - 1
    calc = CustomsCalculator(eur_rate=1.0, tariffs=SAMPLE_TARIFFS)
    first = calc.calculate_ctp(
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type=FuelType.GASOLINE,
        power_hp=150,
    )
    second = calc.calculate_ctp(
        price_eur=5_000,
        engine_cc=1_600,
        year=year,
        car_type=FuelType.GASOLINE,
        power_hp=100,
    )
    assert first["total_eur"] == pytest.approx(11_467.0)
    assert second["total_eur"] == pytest.approx(9_267.0)
    # ensure first result dict not mutated after second calculation
    assert first["total_eur"] == pytest.approx(11_467.0)
