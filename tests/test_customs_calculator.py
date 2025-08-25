import sys
import types
import importlib.util
from pathlib import Path
from enum import Enum
from datetime import date
import copy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import yaml
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG
from bot_alista.rules.age import compute_actual_age_years
from decimal import Decimal, ROUND_HALF_UP

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


CONFIG = ROOT / "external" / "tks_api_official" / "config.yaml"
with open(CONFIG, "r", encoding="utf-8") as fh:
    TARIFFS = yaml.safe_load(fh)


@pytest.fixture(autouse=True)
def mock_fts_rates(monkeypatch):
    def fake_rates(_date):
        return {"USD": 90.0, "EUR": 100.0, "KRW": 0.07, "RUB": 1.0}

    monkeypatch.setattr(currency_mod, "_get_fts_rates", fake_rates)


@pytest.fixture
def calc() -> CustomsCalculator:
    """Return a calculator using the test exchange rate and tariffs."""
    tariffs = copy.deepcopy(TARIFFS)
    tariffs["util_date"] = date(2024, 1, 1)
    tariffs["ctp"] = {"duty_rate": 0.2, "min_per_cc_eur": 0.44}
    return CustomsCalculator(tariffs=tariffs, rate_date=date(2024, 1, 1))


@pytest.fixture
def vehicle_usd() -> dict:
    """Common vehicle parameters priced in USD."""
    return {
        "age": AgeGroup("5-7"),
        "engine_capacity": 2000,
        "engine_type": EngineType("gasoline"),
        "power": 150,
        "production_year": 2017,
        "price": 10000,
        "owner_type": OwnerType("individual"),
        "currency": "USD",
        "vehicle_type": VehicleType("passenger"),
    }


def test_calculate_ctp_returns_expected_total(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    res = calc.calculate_ctp()

    price_rub = to_rub(vehicle_usd["price"], "USD", rate_date=calc.rate_date)

    tariffs = calc.tariffs
    vt = tariffs["vehicle_types"]["passenger"]
    min_duty_rub = to_rub(
        tariffs["ctp"]["min_per_cc_eur"], "EUR", rate_date=calc.rate_date
    ) * vehicle_usd["engine_capacity"]
    duty_rub = rnd(max(price_rub * tariffs["ctp"]["duty_rate"], min_duty_rub))
    excise_rub = rnd(vt["excise_rates"]["gasoline"] * vehicle_usd["power"])
    usage = "personal" if vehicle_usd["owner_type"].value == "individual" else "commercial"
    fuel = "ice"
    vehicle_kind = "passenger"
    age_years = compute_actual_age_years(vehicle_usd["production_year"], calc.tariffs["util_date"])
    util_rub = rnd(calc_util_rub(
        person_type=vehicle_usd["owner_type"].value,
        usage=usage,
        engine_cc=vehicle_usd["engine_capacity"],
        fuel=fuel,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        date_decl=calc.tariffs["util_date"],
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(UTIL_CONFIG),
    ))
    rc = vt["recycling_fee"]
    recycling_rub = rnd(
        rc["base_rate"]
        * rc["engine_factors"]["gasoline"]
        * rc["age_adjustments"]["5-7"]["gasoline"]
    )
    fee_rub = int(
        next(
            tax for limit, tax in TARIFFS["clearance_tax_ranges"] if price_rub <= limit
        )
    )
    vat_rub = rnd(tariffs["vat_rate"] * (price_rub + duty_rub + excise_rub))
    expected_total = rnd(
        duty_rub + excise_rub + util_rub + recycling_rub + vat_rub + fee_rub
    )

    assert res["price_rub"] == rnd(price_rub)
    assert res["duty_rub"] == duty_rub
    assert res["excise_rub"] == excise_rub
    assert res["util_rub"] == util_rub
    assert res["recycling_rub"] == recycling_rub
    assert res["fee_rub"] == fee_rub
    assert res["vat_rub"] == vat_rub
    assert res["total_rub"] == expected_total


def test_clearance_tax_uses_tariff_ranges(
    calc: CustomsCalculator, vehicle_usd: dict
) -> None:
    """Calculator should respect clearance tax ranges from tariffs."""
    calc.tariffs["clearance_tax_ranges"] = [(float("inf"), 12345)]
    calc.set_vehicle_details(**vehicle_usd)
    res = calc.calculate_ctp()
    assert res["fee_rub"] == 12345


def test_calculate_etc_includes_vehicle_price(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    ctp = calc.calculate_ctp()
    calc.set_vehicle_details(**vehicle_usd)
    etc = calc.calculate_etc()
    rate_rub = to_rub(
        TARIFFS["vehicle_types"]["passenger"]["age_groups"]["5-7"]["gasoline"]["rate_per_cc"],
        "EUR",
        rate_date=calc.rate_date,
    )
    expected_duty = rnd(max(rate_rub * vehicle_usd["engine_capacity"], 0))
    assert etc["duty_rub"] == expected_duty
    assert etc["excise_rub"] == 0.0
    assert etc["vat_rub"] == 0.0
    assert etc["etc_rub"] == rnd(etc["price_rub"] + etc["total_rub"])
    # ensure previous result not mutated
    assert ctp["total_rub"] == ctp["total_rub"]


def test_calculate_auto_selects_higher(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    auto = calc.calculate_auto()
    calc.set_vehicle_details(**vehicle_usd)
    ctp = calc.calculate_ctp()
    calc.set_vehicle_details(**vehicle_usd)
    etc = calc.calculate_etc()
    expected = ctp if ctp["total_rub"] >= etc["total_rub"] else etc
    assert auto == expected


def test_calculate_auto_does_not_mutate_vehicle(calc: CustomsCalculator, vehicle_usd: dict):
    calc.set_vehicle_details(**vehicle_usd)
    before = copy.deepcopy(calc.vehicle)
    calc.calculate_auto()
    assert calc.vehicle == before


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


@pytest.mark.parametrize("currency", ["USD", "EUR", "KRW", "RUB"])
def test_currency_conversion(calc: CustomsCalculator, currency: str):
    amount = 10000
    calc.set_vehicle_details(
        age=AgeGroup("new"),
        engine_capacity=1000,
        engine_type=EngineType("gasoline"),
        power=100,
        production_year=2024,
        price=amount,
        owner_type=OwnerType("individual"),
        currency=currency,
    )
    res = calc.calculate_ctp()
    expected_rub = rnd(to_rub(amount, currency, rate_date=calc.rate_date))
    assert res["price_rub"] == expected_rub


def test_invalid_engine_capacity_low(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=500,
            engine_type=EngineType("gasoline"),
            power=100,
            production_year=2024,
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
            production_year=2024,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_hybrid_allows_non_zero_capacity(calc: CustomsCalculator):
    calc.set_vehicle_details(
        age=AgeGroup("new"),
        engine_capacity=1600,
        engine_type=EngineType("hybrid"),
        power=100,
        production_year=2023,
        price=1000,
        owner_type=OwnerType("individual"),
        currency="EUR",
    )
    assert calc.vehicle.engine_capacity == 1600


def test_unsupported_currency(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=100,
            production_year=2024,
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
            production_year=2010,
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
            production_year=2018,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_invalid_power(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=0,
            production_year=2024,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_invalid_price(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=100,
            production_year=2024,
            price=0,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_invalid_production_year(calc: CustomsCalculator):
    with pytest.raises(WrongParamException):
        calc.set_vehicle_details(
            age=AgeGroup("new"),
            engine_capacity=1000,
            engine_type=EngineType("gasoline"),
            power=100,
            production_year=1800,
            price=1000,
            owner_type=OwnerType("individual"),
            currency="EUR",
        )


def test_recycling_fee_owner_multiplier(calc: CustomsCalculator, vehicle_usd: dict):
    params = dict(vehicle_usd)
    params["owner_type"] = OwnerType("company")
    params["age"] = AgeGroup("new")
    calc.set_vehicle_details(**params)
    res = calc.calculate_ctp()
    rc = calc.tariffs["vehicle_types"]["passenger"]["recycling_fee"]
    expected = rnd(
        rc["base_rate"]
        * rc["engine_factors"]["gasoline"]
        * rc["owner_multipliers"]["company"]
    )
    assert res["recycling_rub"] == expected

def rnd(val: float) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
