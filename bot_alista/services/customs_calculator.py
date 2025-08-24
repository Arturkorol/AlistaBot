"""RUB based customs calculation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from tabulate import tabulate

from .currency import to_rub
from .tariffs import get_tariffs

logger = logging.getLogger(__name__)


BASE_VAT = 0.2
RECYCLING_FEE_BASE_RATE = 20_000
CUSTOMS_CLEARANCE_TAX_RANGES = [
    (200_000, 1_067),
    (450_000, 2_134),
    (1_200_000, 4_269),
    (3_000_000, 11_746),
    (5_000_000, 16_524),
    (7_000_000, 20_000),
    (float("inf"), 30_000),
]


class WrongParamException(Exception):
    """Exception raised for invalid parameters."""

    def __init__(self, message: str):
        super().__init__(message)
        logger.error(message)


class EnginePowerUnit(Enum):
    KW = "kilowatt"
    HP = "horsepower"


class EngineType(Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class VehicleAge(Enum):
    NEW = "new"
    ONE_TO_THREE = "1-3"
    THREE_TO_FIVE = "3-5"
    FIVE_TO_SEVEN = "5-7"
    OVER_SEVEN = "over_7"


class VehicleOwnerType(Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


@dataclass
class _Vehicle:
    age: VehicleAge
    engine_capacity: int
    engine_type: EngineType
    power: int
    price_rub: float
    owner_type: VehicleOwnerType
    currency: str


class CustomsCalculator:
    """Customs Calculator for vehicle import duties."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        tariffs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.tariffs = tariffs or get_tariffs(config_path)
        self.reset_fields()
        self._last_result: Dict[str, float] | None = None

    # ------------------------------------------------------------------
    # Vehicle state
    # ------------------------------------------------------------------
    def reset_fields(self) -> None:
        self.vehicle: Optional[_Vehicle] = None

    def set_vehicle_details(
        self,
        age: str | VehicleAge,
        engine_capacity: int,
        engine_type: str | EngineType,
        power: int,
        price: float,
        owner_type: str | VehicleOwnerType,
        currency: str = "USD",
    ) -> None:
        try:
            age_enum = age if isinstance(age, VehicleAge) else VehicleAge(age)
            engine_enum = (
                engine_type if isinstance(engine_type, EngineType) else EngineType(engine_type)
            )
            owner_enum = (
                owner_type if isinstance(owner_type, VehicleOwnerType) else VehicleOwnerType(owner_type)
            )
        except ValueError as exc:
            raise WrongParamException(str(exc))

        if engine_capacity < 800 or engine_capacity > 8000:
            raise WrongParamException("engine_capacity out of range")

        try:
            price_rub = to_rub(price, currency)
        except Exception as exc:
            raise WrongParamException(str(exc))

        self.vehicle = _Vehicle(
            age=age_enum,
            engine_capacity=int(engine_capacity),
            engine_type=engine_enum,
            power=int(power),
            price_rub=float(price_rub),
            owner_type=owner_enum,
            currency=currency.upper(),
        )

    def _require_vehicle(self) -> _Vehicle:
        if not self.vehicle:
            raise WrongParamException("Vehicle details not set")
        return self.vehicle

    # ------------------------------------------------------------------
    # Fee helpers
    # ------------------------------------------------------------------
    def calculate_clearance_tax(self) -> float:
        v = self._require_vehicle()
        price = v.price_rub
        for limit, tax in CUSTOMS_CLEARANCE_TAX_RANGES:
            if price <= limit:
                logger.info("Customs clearance tax: %s RUB", tax)
                return float(tax)
        return float(CUSTOMS_CLEARANCE_TAX_RANGES[-1][1])

    def calculate_recycling_fee(self) -> float:
        v = self._require_vehicle()
        factors = self.tariffs["recycling_factors"]
        default = factors.get("default", {})
        adjustments = factors.get("adjustments", {}).get(v.age.value, {})
        engine_factor = adjustments.get(
            v.engine_type.value, default.get(v.engine_type.value, 1.0)
        )
        fee = RECYCLING_FEE_BASE_RATE * engine_factor
        logger.info("Recycling fee: %s RUB", fee)
        return float(fee)

    def calculate_excise(self) -> float:
        v = self._require_vehicle()
        rate = self.tariffs["excise_rates"].get(v.engine_type.value, 0)
        excise = rate * v.power
        logger.info("Excise: %s RUB", excise)
        return float(excise)

    # ------------------------------------------------------------------
    # Calculation modes
    # ------------------------------------------------------------------
    def calculate_ctp(self) -> Dict[str, float]:
        v = self._require_vehicle()
        price_rub = v.price_rub
        vat_rate = self.tariffs.get("vat_rate", BASE_VAT)

        duty_rate = 0.2
        min_duty_per_cc = to_rub(0.44, "EUR")
        duty_rub = max(price_rub * duty_rate, min_duty_per_cc * v.engine_capacity)

        excise = self.calculate_excise()
        recycling_fee = self.calculate_recycling_fee()
        vat = (price_rub + duty_rub + excise) * vat_rate

        clearance_fee = self.calculate_clearance_tax()
        util_fee = self.tariffs["base_util_fee"] * self.tariffs.get(
            "ctp_util_coeff_base", 1.0
        )

        total_pay = duty_rub + excise + vat + clearance_fee + util_fee + recycling_fee
        res = {
            "price_rub": price_rub,
            "duty_rub": duty_rub,
            "excise_rub": excise,
            "vat_rub": vat,
            "fee_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total_pay,
        }
        self._last_result = res
        return res

    def calculate_etc(self) -> Dict[str, float]:
        v = self._require_vehicle()
        cfg = self.tariffs["age_groups"][v.age.value][v.engine_type.value]
        rate_per_cc = cfg["rate_per_cc"]
        min_duty = cfg.get("min_duty", 0)
        duty_rub = max(rate_per_cc * v.engine_capacity, min_duty)

        clearance_fee = self.calculate_clearance_tax()
        util_fee = self.tariffs["base_util_fee"] * self.tariffs.get(
            "etc_util_coeff_base", 1.0
        )
        recycling_fee = self.calculate_recycling_fee()

        total_pay = duty_rub + clearance_fee + util_fee + recycling_fee
        res = {
            "duty_rub": duty_rub,
            "fee_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total_pay,
            "vehicle_price_rub": v.price_rub,
            "etc_rub": v.price_rub + total_pay,
        }
        self._last_result = res
        return res

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------
    def print_table(self, mode: str) -> str:
        if mode.upper() == "ETC":
            data = self.calculate_etc()
        elif mode.upper() == "CTP":
            data = self.calculate_ctp()
        else:
            raise WrongParamException("Invalid calculation mode")

        table = [
            [k, f"{v:,.2f}" if isinstance(v, (int, float)) else v]
            for k, v in data.items()
        ]
        formatted = tabulate(table, headers=["Description", "Amount"], tablefmt="psql")
        logger.debug("\n%s", formatted)
        return formatted


__all__ = [
    "CustomsCalculator",
    "EnginePowerUnit",
    "EngineType",
    "VehicleAge",
    "VehicleOwnerType",
    "WrongParamException",
]

