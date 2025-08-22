import yaml
from pathlib import Path
from datetime import datetime
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services import calculate_ctp, calculate_etc, CustomsCalculator


CONFIG = Path(__file__).resolve().parents[1] / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    SAMPLE_TARIFFS = yaml.safe_load(fh)


def test_wrapper_matches_class_result():
    year = datetime.now().year - 1
    kwargs = dict(price_eur=10_000, engine_cc=2_000, year=year, car_type="Бензин", power_hp=150)
    calc = CustomsCalculator(eur_rate=1.0, tariffs=SAMPLE_TARIFFS)
    class_result = calc.calculate_ctp(**kwargs)
    func_result = calculate_ctp(eur_rate=1.0, tariffs=SAMPLE_TARIFFS, **kwargs)
    assert func_result == class_result


def test_calculate_etc_wrapper_adds_vehicle_price():
    year = datetime.now().year - 1
    kwargs = dict(price_eur=10_000, engine_cc=2_000, year=year, car_type="Бензин", power_hp=150)
    ctp = calculate_ctp(eur_rate=1.0, tariffs=SAMPLE_TARIFFS, **kwargs)
    etc = calculate_etc(eur_rate=1.0, tariffs=SAMPLE_TARIFFS, **kwargs)
    assert etc["etc_eur"] == pytest.approx(kwargs["price_eur"] + ctp["total_eur"])


def test_wrapper_state_isolated():
    year = datetime.now().year - 1
    first = calculate_ctp(
        eur_rate=1.0,
        tariffs=SAMPLE_TARIFFS,
        price_eur=10_000,
        engine_cc=2_000,
        year=year,
        car_type="Бензин",
        power_hp=150,
    )
    second = calculate_ctp(
        eur_rate=1.0,
        tariffs=SAMPLE_TARIFFS,
        price_eur=5_000,
        engine_cc=1_600,
        year=year,
        car_type="Бензин",
        power_hp=100,
    )
    assert first is not second
    assert first["total_eur"] == pytest.approx(11_467.0)
    assert second["total_eur"] == pytest.approx(9_267.0)
    # ensure first result dict not mutated after second calculation
    assert first["total_eur"] == pytest.approx(11_467.0)

