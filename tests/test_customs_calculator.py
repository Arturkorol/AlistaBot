import yaml
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services.customs_calculator import CustomsCalculator
from bot_alista.services.currency import to_eur
CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    TARIFFS = yaml.safe_load(fh)


def setup_calc():
    return CustomsCalculator(eur_rate=100.0, tariffs=TARIFFS)


def test_calculate_ctp_returns_expected_total():
    calc = setup_calc()
    price_usd = 10000
    price_eur = to_eur(price_usd, "USD")
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=price_usd,
        owner_type="individual",
        currency="USD",
    )
    res = calc.calculate_ctp()

    tariffs = TARIFFS
    duty = max(
        2000 * tariffs["age_groups"]["5-7"]["gasoline"]["rate_per_cc"],
        tariffs["age_groups"]["5-7"]["gasoline"]["min_duty"],
    )
    excise = tariffs["excise_rates"]["gasoline"] * 150 / 100.0
    util = (
        tariffs["base_util_fee"]
        * tariffs["ctp_util_coeff_base"]
        * tariffs["recycling_factors"]["adjustments"]["5-7"]["gasoline"]
        / 100.0
    )
    fee = tariffs["base_clearance_fee"] / 100.0
    vat = tariffs["vat_rate"] * (price_eur + duty + excise + util + fee)
    expected_total = duty + excise + util + vat + fee

    assert res["total_eur"] == pytest.approx(expected_total)


def test_calculate_etc_includes_vehicle_price():
    calc = setup_calc()
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        owner_type="individual",
        currency="USD",
    )
    ctp = calc.calculate_ctp()
    etc = calc.calculate_etc()
    assert etc["etc_eur"] == pytest.approx(etc["vehicle_price_eur"] + etc["total_eur"])
    # ensure previous result not mutated
    assert ctp["total_eur"] == pytest.approx(ctp["total_eur"])


def test_state_reset_between_calls():
    calc = setup_calc()
    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=2000,
        engine_type="gasoline",
        power=150,
        price=10000,
        owner_type="individual",
        currency="USD",
    )
    first = calc.calculate_ctp()

    calc.set_vehicle_details(
        age="5-7",
        engine_capacity=1600,
        engine_type="gasoline",
        power=100,
        price=5000,
        owner_type="individual",
        currency="USD",
    )
    second = calc.calculate_ctp()

    assert first["total_eur"] != second["total_eur"]
    assert first["total_eur"] == pytest.approx(first["total_eur"])


@pytest.mark.parametrize("currency, rate", [
    ("USD", 0.9),
    ("EUR", 1.0),
    ("KRW", 0.0007),
    ("RUB", 0.01),
])
def test_currency_conversion(currency, rate):
    calc = setup_calc()
    amount = 10000
    calc.set_vehicle_details(
        age="new",
        engine_capacity=1000,
        engine_type="gasoline",
        power=100,
        price=amount,
        owner_type="individual",
        currency=currency,
    )
    res = calc.calculate_ctp()
    assert res["price_eur"] == pytest.approx(amount * rate)


def test_invalid_engine_capacity_low():
    calc = setup_calc()
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age="new",
            engine_capacity=500,
            engine_type="gasoline",
            power=100,
            price=1000,
            owner_type="individual",
            currency="EUR",
        )


def test_invalid_engine_capacity_high():
    calc = setup_calc()
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age="new",
            engine_capacity=9000,
            engine_type="gasoline",
            power=100,
            price=1000,
            owner_type="individual",
            currency="EUR",
        )


def test_unsupported_currency():
    calc = setup_calc()
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age="new",
            engine_capacity=1000,
            engine_type="gasoline",
            power=100,
            price=1000,
            owner_type="individual",
            currency="ABC",
        )


def test_unsupported_age_group():
    calc = setup_calc()
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age="over_10",
            engine_capacity=1000,
            engine_type="gasoline",
            power=100,
            price=1000,
            owner_type="individual",
            currency="EUR",
        )

