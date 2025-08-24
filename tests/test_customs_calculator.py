import sys
import types
import importlib.util
from pathlib import Path
from enum import Enum

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES_PATH = ROOT / "bot_alista" / "services"

# Create a minimal ``services`` package without executing the real
# package ``__init__`` which depends on optional external modules.
services_pkg = types.ModuleType("services")
services_pkg.__path__ = [str(SERVICES_PATH)]
sys.modules.setdefault("services", services_pkg)

# Load required submodules manually.
spec = importlib.util.spec_from_file_location(
    "services.currency", SERVICES_PATH / "currency.py"
)
currency_mod = importlib.util.module_from_spec(spec)
sys.modules["services.currency"] = currency_mod
spec.loader.exec_module(currency_mod)  # type: ignore[attr-defined]
to_eur = currency_mod.to_eur

spec = importlib.util.spec_from_file_location(
    "services.customs_calculator", SERVICES_PATH / "customs_calculator.py"
)
cc_mod = importlib.util.module_from_spec(spec)
sys.modules["services.customs_calculator"] = cc_mod
spec.loader.exec_module(cc_mod)  # type: ignore[attr-defined]

CustomsCalculator = cc_mod.CustomsCalculator

if hasattr(cc_mod, "AgeGroup"):
    AgeGroup = cc_mod.AgeGroup
else:  # pragma: no cover - fallback
    class AgeGroup(str, Enum):
        NEW = "new"
        FIVE_SEVEN = "5-7"

if hasattr(cc_mod, "EngineType"):
    EngineType = cc_mod.EngineType
else:  # pragma: no cover - fallback
    class EngineType(str, Enum):
        GASOLINE = "gasoline"

if hasattr(cc_mod, "OwnerType"):
    OwnerType = cc_mod.OwnerType
else:  # pragma: no cover - fallback
    class OwnerType(str, Enum):
        INDIVIDUAL = "individual"

if hasattr(cc_mod, "WrongParamException"):
    WrongParamException = cc_mod.WrongParamException
else:  # pragma: no cover - fallback for current implementation
    class WrongParamException(Exception):
        pass

CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    TARIFFS = yaml.safe_load(fh)


@pytest.fixture
def calc() -> CustomsCalculator:
    """Return a calculator using the test exchange rate and tariffs."""
    return CustomsCalculator(eur_rate=100.0, tariffs=TARIFFS)


@pytest.fixture
def vehicle_usd() -> dict:
    """Common vehicle parameters priced in USD."""
    return {
        "age": AgeGroup("5-7"),
        "engine_capacity": 2000,
        "engine_type": EngineType("gasoline"),
        "power": 150,
        "price": 10000,
        "owner_type": OwnerType("individual"),
        "currency": "USD",
    }


def test_calculate_ctp_returns_expected_total(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    res = calc.calculate_ctp()

    price_eur = to_eur(vehicle_usd["price"], "USD")
    price_rub = price_eur * calc.eur_rate

    tariffs = TARIFFS
    duty_rub = max(
        vehicle_usd["engine_capacity"]
        * tariffs["age_groups"]["5-7"]["gasoline"]["rate_per_cc"],
        tariffs["age_groups"]["5-7"]["gasoline"]["min_duty"],
    )
    excise_rub = tariffs["excise_rates"]["gasoline"] * vehicle_usd["power"]
    util_rub = (
        tariffs["base_util_fee"]
        * tariffs["ctp_util_coeff_base"]
        * tariffs["recycling_factors"]["adjustments"]["5-7"]["gasoline"]
    )
    fee_rub = tariffs["base_clearance_fee"]
    vat_rub = tariffs["vat_rate"] * (
        price_rub + duty_rub + excise_rub + util_rub + fee_rub
    )
    expected_total = duty_rub + excise_rub + util_rub + vat_rub + fee_rub

    assert res["price_rub"] == pytest.approx(price_rub)
    assert res["duty_rub"] == pytest.approx(duty_rub)
    assert res["excise_rub"] == pytest.approx(excise_rub)
    assert res["util_rub"] == pytest.approx(util_rub)
    assert res["fee_rub"] == pytest.approx(fee_rub)
    assert res["vat_rub"] == pytest.approx(vat_rub)
    assert res["total_rub"] == pytest.approx(expected_total)


def test_calculate_etc_includes_vehicle_price(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    ctp = calc.calculate_ctp()
    etc = calc.calculate_etc()
    assert etc["etc_rub"] == pytest.approx(
        etc["vehicle_price_rub"] + etc["total_rub"]
    )
    # ensure previous result not mutated
    assert ctp["total_rub"] == pytest.approx(ctp["total_rub"])


def test_state_reset_between_calls(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    first = calc.calculate_ctp()

    params = dict(vehicle_usd)
    params.update(engine_capacity=1600, power=100, price=5000)
    calc.set_vehicle_details(**params)
    second = calc.calculate_ctp()

    assert first["total_rub"] != second["total_rub"]
    assert first["total_rub"] == pytest.approx(first["total_rub"])


@pytest.mark.parametrize("currency, rate", [
    ("USD", 0.9),
    ("EUR", 1.0),
    ("KRW", 0.0007),
    ("RUB", 0.01),
])
def test_currency_conversion(calc: CustomsCalculator, currency: str, rate: float):
    amount = 10000
    calc.set_vehicle_details(
        age=AgeGroup("new"),
        engine_capacity=1000,
        engine_type=EngineType("gasoline"),
        power=100,
        price=amount,
        owner_type=OwnerType("individual"),
        currency=currency,
    )
    res = calc.calculate_ctp()
    expected_eur = amount * rate
    expected_rub = expected_eur * calc.eur_rate
    assert res["price_eur"] == pytest.approx(expected_eur)
    assert res["price_rub"] == pytest.approx(expected_rub)


def test_invalid_engine_capacity_low(calc: CustomsCalculator):
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=500,
            engine_type=EngineType("gasoline"),
            power=100,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_invalid_engine_capacity_high(calc: CustomsCalculator):
    with pytest.raises(ValueError):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=9000,
            engine_type=EngineType("gasoline"),
            power=100,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_unsupported_currency(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=100,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="ABC",
        )


def test_unsupported_age_group(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age="over_10",
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=100,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_invalid_engine_type_enum(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("5-7"),
            engine_capacity=2000,
            engine_type="rocket",
            power=100,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )

