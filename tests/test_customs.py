import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot_alista.services.customs import calculate_customs
import pytest


def test_new_petrol_vehicle():
    res = calculate_customs(
        price_eur=20000,
        engine_cc=2000,
        year=2023,
        car_type="Бензин",
        power_hp=200,
        eur_rate=100,
        eco_class="Euro5",
        is_new=True,
        vehicle_category="M1",
    )
    assert res["duty_eur"] == pytest.approx(9600.0)
    assert res["vat_eur"] == pytest.approx(5922.0)
    assert res["util_eur"] == pytest.approx(10.0)
    assert res["total_eur"] == pytest.approx(15537.0)


def test_used_vehicle_over_five_years():
    res = calculate_customs(
        price_eur=5000,
        engine_cc=2500,
        year=2010,
        car_type="Бензин",
        power_hp=200,
        eur_rate=100,
        eco_class="Euro3",
        is_new=False,
        vehicle_category="M1",
    )
    assert res["duty_eur"] == pytest.approx(12500.0)
    assert res["vat_eur"] == pytest.approx(3506.8)
    assert res["util_eur"] == pytest.approx(34.0)
    assert res["total_eur"] == pytest.approx(16045.8)
