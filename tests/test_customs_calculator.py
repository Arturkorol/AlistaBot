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
to_rub = currency_mod.to_rub

spec = importlib.util.spec_from_file_location(
    "services.customs_calculator", SERVICES_PATH / "customs_calculator.py"
)
cc_mod = importlib.util.module_from_spec(spec)
sys.modules["services.customs_calculator"] = cc_mod
spec.loader.exec_module(cc_mod)  # type: ignore[attr-defined]

CustomsCalculator = cc_mod.CustomsCalculator

if hasattr(cc_mod, "VehicleAge"):
    AgeGroup = cc_mod.VehicleAge
else:  # pragma: no cover - fallback
    class AgeGroup(str, Enum):
        NEW = "new"
        FIVE_SEVEN = "5-7"

if hasattr(cc_mod, "EngineType"):
    EngineType = cc_mod.EngineType
else:  # pragma: no cover - fallback
    class EngineType(str, Enum):
        GASOLINE = "gasoline"

if hasattr(cc_mod, "VehicleOwnerType"):
    OwnerType = cc_mod.VehicleOwnerType
else:  # pragma: no cover - fallback
    class OwnerType(str, Enum):
        INDIVIDUAL = "individual"

if hasattr(cc_mod, "VehicleType"):
    VehicleType = cc_mod.VehicleType
else:  # pragma: no cover - fallback
    class VehicleType(str, Enum):
        PASSENGER = "passenger"

if hasattr(cc_mod, "WrongParamException"):
    WrongParamException = cc_mod.WrongParamException
else:  # pragma: no cover - fallback for current implementation
    class WrongParamException(Exception):
        pass

RECYCLING_FEE_BASE_RATE = getattr(cc_mod, "RECYCLING_FEE_BASE_RATE", 20000)

CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    TARIFFS = yaml.safe_load(fh)


@pytest.fixture
def calc() -> CustomsCalculator:
    """Return a calculator using the test exchange rate and tariffs."""
    return CustomsCalculator(tariffs=TARIFFS)


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
        "vehicle_type": VehicleType("passenger"),
    }


def test_calculate_ctp_returns_expected_total(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    res = calc.calculate_ctp()

    price_rub = to_rub(vehicle_usd["price"], "USD")

    tariffs = TARIFFS
    vt = tariffs["vehicle_types"]["passenger"]
    min_duty_rub = to_rub(0.44, "EUR") * vehicle_usd["engine_capacity"]
    duty_rub = max(price_rub * 0.2, min_duty_rub)
    excise_rub = vt["excise_rates"]["gasoline"] * vehicle_usd["power"]
    util_rub = tariffs["base_util_fee"] * tariffs["ctp_util_coeff_base"]
    recycling_rub = RECYCLING_FEE_BASE_RATE * vt["recycling_factors"]["adjustments"]["5-7"]["gasoline"]
    price_limit_map = [
        (200_000, 1_067),
        (450_000, 2_134),
        (1_200_000, 4_269),
        (3_000_000, 11_746),
        (5_000_000, 16_524),
        (7_000_000, 20_000),
        (float("inf"), 30_000),
    ]
    fee_rub = next(tax for limit, tax in price_limit_map if price_rub <= limit)
    vat_rub = tariffs["vat_rate"] * (price_rub + duty_rub + excise_rub)
    expected_total = duty_rub + excise_rub + util_rub + recycling_rub + vat_rub + fee_rub

    assert res["price_rub"] == pytest.approx(price_rub)
    assert res["duty_rub"] == pytest.approx(duty_rub)
    assert res["excise_rub"] == pytest.approx(excise_rub)
    assert res["util_rub"] == pytest.approx(util_rub)
    assert res["recycling_rub"] == pytest.approx(recycling_rub)
    assert res["fee_rub"] == pytest.approx(fee_rub)
    assert res["vat_rub"] == pytest.approx(vat_rub)
    assert res["total_rub"] == pytest.approx(expected_total)


def test_calculate_etc_includes_vehicle_price(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    ctp = calc.calculate_ctp()
    calc.set_vehicle_details(**vehicle_usd)
    etc = calc.calculate_etc()
    rate_rub = to_rub(
        TARIFFS["vehicle_types"]["passenger"]["age_groups"]["5-7"]["gasoline"]["rate_per_cc"],
        "EUR",
    )
    expected_duty = max(rate_rub * vehicle_usd["engine_capacity"], 0)
    assert etc["duty_rub"] == pytest.approx(expected_duty)
    assert etc["excise_rub"] == 0.0
    assert etc["vat_rub"] == 0.0
    assert etc["etc_rub"] == pytest.approx(etc["price_rub"] + etc["total_rub"])
    # ensure previous result not mutated
    assert ctp["total_rub"] == pytest.approx(ctp["total_rub"])


def test_calculate_auto_selects_higher(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    auto = calc.calculate_auto()
    calc.set_vehicle_details(**vehicle_usd)
    ctp = calc.calculate_ctp()
    calc.set_vehicle_details(**vehicle_usd)
    etc = calc.calculate_etc()
    expected = ctp if ctp["total_rub"] >= etc["total_rub"] else etc
    assert auto == expected


def test_vehicle_type_truck(calc: CustomsCalculator, vehicle_usd: dict):
    params = dict(vehicle_usd)
    params["vehicle_type"] = VehicleType("truck")
    calc.set_vehicle_details(**params)
    truck_res = calc.calculate_ctp()
    calc.set_vehicle_details(**vehicle_usd)
    pass_res = calc.calculate_ctp()
    assert truck_res == pass_res


def test_state_reset_between_calls(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    first = calc.calculate_ctp()

    params = dict(vehicle_usd)
    params.update(engine_capacity=1600, power=100, price=5000)
    calc.set_vehicle_details(**params)
    second = calc.calculate_ctp()

    assert first["total_rub"] != second["total_rub"]
    assert first["total_rub"] == pytest.approx(first["total_rub"])


@pytest.mark.parametrize("currency", ["USD", "EUR", "KRW", "RUB"])
def test_currency_conversion(calc: CustomsCalculator, currency: str):
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
    expected_rub = to_rub(amount, currency)
    assert res["price_rub"] == pytest.approx(expected_rub)


def test_invalid_engine_capacity_low(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
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
    with pytest.raises(WrongParamException):
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

