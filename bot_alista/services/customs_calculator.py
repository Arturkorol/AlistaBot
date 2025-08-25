"""RUB based customs calculation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import date
import copy

from tabulate import tabulate

from .currency import to_rub
from .tariffs import get_tariffs
from bot_alista.clearance_fee import (
    CLEARANCE_FEE_RANGES,
    calc_clearance_fee_rub,
)
from bot_alista.tariff.util_fee import calc_util_rub, UTIL_CONFIG

logger = logging.getLogger(__name__)


BASE_VAT = 0.2
RECYCLING_FEE_BASE_RATE = 20_000


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


class VehicleType(Enum):
    PASSENGER = "passenger"
    TRUCK = "truck"


@dataclass
class _Vehicle:
    age: VehicleAge
    engine_capacity: int
    engine_type: EngineType
    power: int
    price_rub: float
    owner_type: VehicleOwnerType
    currency: str
    vehicle_type: VehicleType


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
        vehicle_type: str | VehicleType = "passenger",
    ) -> None:
        try:
            age_enum = age if isinstance(age, VehicleAge) else VehicleAge(age)
            engine_enum = (
                engine_type if isinstance(engine_type, EngineType) else EngineType(engine_type)
            )
            owner_enum = (
                owner_type if isinstance(owner_type, VehicleOwnerType) else VehicleOwnerType(owner_type)
            )
            vehicle_type_enum = (
                vehicle_type
                if isinstance(vehicle_type, VehicleType)
                else VehicleType(vehicle_type)
            )
        except ValueError as exc:
            raise WrongParamException(str(exc))

        if engine_enum in (EngineType.ELECTRIC, EngineType.HYBRID):
            if engine_capacity != 0:
                raise WrongParamException(
                    "engine_capacity must be 0 for electric/hybrid vehicles"
                )
        elif engine_capacity < 800 or engine_capacity > 8000:
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
            vehicle_type=vehicle_type_enum,
        )

    def _require_vehicle(self) -> _Vehicle:
        if not self.vehicle:
            raise WrongParamException("Vehicle details not set")
        return self.vehicle

    def _vehicle_tariffs(self, v: _Vehicle) -> Dict[str, Any]:
        vt = self.tariffs.get("vehicle_types")
        if vt:
            return vt[v.vehicle_type.value]
        return self.tariffs

    # ------------------------------------------------------------------
    # Fee helpers
    # ------------------------------------------------------------------
    def _calculate_util_fee(self, v: _Vehicle) -> float:
        fuel = (
            "ev"
            if v.engine_type is EngineType.ELECTRIC
            else "hybrid"
            if v.engine_type is EngineType.HYBRID
            else "ice"
        )
        vehicle_kind = "passenger"
        usage = (
            "personal"
            if v.owner_type is VehicleOwnerType.INDIVIDUAL
            else "commercial"
        )
        age_map = {
            VehicleAge.NEW: 0.0,
            VehicleAge.ONE_TO_THREE: 2.0,
            VehicleAge.THREE_TO_FIVE: 4.0,
            VehicleAge.FIVE_TO_SEVEN: 6.0,
            VehicleAge.OVER_SEVEN: 8.0,
        }
        age_years = age_map.get(v.age, 0.0)

        decl_date = self.tariffs.get("util_date", date(2024, 1, 1))
        if isinstance(decl_date, str):
            decl_date = date.fromisoformat(decl_date)
        util_cfg = copy.deepcopy(UTIL_CONFIG)
        if self.tariffs.get("util_not_in_list"):
            util_cfg["not_in_list"] = True
        avg_cost = self.tariffs.get("avg_vehicle_cost_rub")
        actual_cost = self.tariffs.get("actual_costs_rub")

        return calc_util_rub(
            person_type=v.owner_type.value,
            usage=usage,
            engine_cc=v.engine_capacity,
            fuel=fuel,
            vehicle_kind=vehicle_kind,
            age_years=age_years,
            date_decl=decl_date,
            avg_vehicle_cost_rub=avg_cost,
            actual_costs_rub=actual_cost,
            config=util_cfg,
        )

    def calculate_clearance_tax(self) -> float:
        """Return clearance tax based on price ranges defined in tariffs."""
        v = self._require_vehicle()
        price = v.price_rub
        ranges = self.tariffs.get("clearance_tax_ranges", CLEARANCE_FEE_RANGES)
        fee = calc_clearance_fee_rub(price, ranges)
        logger.info("Customs clearance tax: %s RUB", fee)
        return fee

    def calculate_recycling_fee(self) -> float:
        v = self._require_vehicle()
        vt = self._vehicle_tariffs(v)
        factors = vt["recycling_factors"]
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
        vt = self._vehicle_tariffs(v)
        rate = vt["excise_rates"].get(v.engine_type.value, 0)
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
        util_fee = self._calculate_util_fee(v)

        total_pay = duty_rub + excise + vat + clearance_fee + util_fee + recycling_fee
        res = {
            "mode": "CTP",
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
        vt = self._vehicle_tariffs(v)
        cfg = vt["age_groups"][v.age.value][v.engine_type.value]
        rate_per_cc = to_rub(cfg["rate_per_cc"], "EUR")
        min_duty = cfg.get("min_duty", 0)
        min_duty_rub = to_rub(min_duty, "EUR") if min_duty else 0
        duty_rub = max(rate_per_cc * v.engine_capacity, min_duty_rub)

        clearance_fee = self.calculate_clearance_tax()
        util_fee = self._calculate_util_fee(v)
        recycling_fee = self.calculate_recycling_fee()

        total_pay = duty_rub + clearance_fee + util_fee + recycling_fee
        res = {
            "mode": "ETC",
            "price_rub": v.price_rub,
            "duty_rub": duty_rub,
            "excise_rub": 0.0,
            "vat_rub": 0.0,
            "fee_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total_pay,
            "vehicle_price_rub": v.price_rub,
            "etc_rub": v.price_rub + total_pay,
        }
        self._last_result = res
        return res

    def calculate_auto(self) -> Dict[str, float]:
        v = self._require_vehicle()
        if v.owner_type is VehicleOwnerType.COMPANY:
            return self.calculate_ctp()
        etc = self.calculate_etc()
        self.set_vehicle_details(
            age=v.age,
            engine_capacity=v.engine_capacity,
            engine_type=v.engine_type,
            power=v.power,
            price=v.price_rub,
            owner_type=v.owner_type,
            currency="RUB",
            vehicle_type=v.vehicle_type,
        )
        ctp = self.calculate_ctp()
        chosen = ctp if ctp["total_rub"] >= etc["total_rub"] else etc
        self._last_result = chosen
        return chosen

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
    "VehicleType",
    "WrongParamException",
]

