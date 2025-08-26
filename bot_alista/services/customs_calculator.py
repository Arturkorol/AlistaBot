"""RUB based customs calculation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import date
import copy
from decimal import Decimal, ROUND_HALF_UP

from tabulate import tabulate

from .rates import to_rub
from .tariffs import get_tariffs
from bot_alista.clearance_fee import (
    CLEARANCE_FEE_RANGES,
    calc_clearance_fee_rub,
)
from bot_alista.tariff.util_fee import calc_util_rub, load_util_config
from bot_alista.rules.age import compute_actual_age_years

logger = logging.getLogger(__name__)


BASE_VAT = Decimal("0.2")
RECYCLING_FEE_BASE_RATE = Decimal("20000")


def _round2(value: Decimal) -> Decimal:
    """Round monetary values to two decimals using bankers rounding."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    production_year: int
    price_rub: Decimal
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
        self._last_result: Dict[str, Decimal] | None = None

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
        production_year: int,
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

        if engine_enum is EngineType.ELECTRIC:
            if engine_capacity != 0:
                raise WrongParamException(
                    "engine_capacity must be 0 for electric vehicles"
                )
        elif engine_capacity <= 0:
            raise WrongParamException("engine_capacity must be positive")

        if power <= 0:
            raise WrongParamException("power must be positive")
        if price <= 0:
            raise WrongParamException("price must be positive")
        current_year = date.today().year
        if production_year < 1900 or production_year > current_year:
            raise WrongParamException("production_year out of range")

        try:
            price_rub = Decimal(str(to_rub(price, currency)))
        except Exception as exc:
            raise WrongParamException(str(exc))

        self.vehicle = _Vehicle(
            age=age_enum,
            engine_capacity=int(engine_capacity),
            engine_type=engine_enum,
            power=int(power),
            production_year=int(production_year),
            price_rub=price_rub,
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
    def _calculate_util_fee(
        self,
        v: _Vehicle,
        age_years: float,
        decl_date: date,
        multiplier: Decimal = Decimal("1.0"),
    ) -> Decimal:
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

        util_cfg = copy.deepcopy(load_util_config())
        if self.tariffs.get("util_not_in_list"):
            util_cfg["not_in_list"] = True
        avg_cost = self.tariffs.get("avg_vehicle_cost_rub")
        actual_cost = self.tariffs.get("actual_costs_rub")

        fee = Decimal(
            str(
                calc_util_rub(
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
            )
        )
        return fee * (multiplier or Decimal("1.0"))

    def calculate_clearance_tax(self, v: _Vehicle | None = None) -> Decimal:
        """Return clearance tax based on price ranges defined in tariffs."""
        v = v or self._require_vehicle()
        price = v.price_rub
        ranges = self.tariffs.get("clearance_tax_ranges", CLEARANCE_FEE_RANGES)
        fee = Decimal(calc_clearance_fee_rub(float(price), ranges))
        logger.info("Customs clearance tax: %s RUB", fee)
        return fee

    def calculate_recycling_fee(self, v: _Vehicle | None = None) -> Decimal:
        v = v or self._require_vehicle()
        vt = self._vehicle_tariffs(v)
        cfg = vt.get("recycling_fee")
        if cfg:
            base = Decimal(str(cfg.get("base_rate", RECYCLING_FEE_BASE_RATE)))
            engine_factor = Decimal(
                str(cfg.get("engine_factors", {}).get(v.engine_type.value, 1.0))
            )
            age_factor = Decimal(
                str(
                    cfg.get("age_adjustments", {})
                    .get(v.age.value, {})
                    .get(v.engine_type.value, 1.0)
                )
            )
            owner_factor = Decimal(
                str(cfg.get("owner_multipliers", {}).get(v.owner_type.value, 1.0))
            )
            fee = base * engine_factor * age_factor * owner_factor
        else:  # backward compatibility with older configs
            factors = vt.get("recycling_factors", {})
            default = factors.get("default", {})
            adjustments = factors.get("adjustments", {}).get(v.age.value, {})
            engine_factor = Decimal(
                str(adjustments.get(v.engine_type.value, default.get(v.engine_type.value, 1.0)))
            )
            fee = RECYCLING_FEE_BASE_RATE * engine_factor
        fee = _round2(fee)
        logger.info("Recycling fee: %s RUB", fee)
        return fee

    def calculate_excise(self, v: _Vehicle | None = None) -> Decimal:
        v = v or self._require_vehicle()
        vt = self._vehicle_tariffs(v)
        rate = Decimal(str(vt["excise_rates"].get(v.engine_type.value, 0)))
        excise = rate * Decimal(v.power)
        logger.info("Excise: %s RUB", excise)
        return _round2(excise)

    # ------------------------------------------------------------------
    # Calculation modes
    # ------------------------------------------------------------------
    def _calc_ctp(self, v: _Vehicle) -> Dict[str, Decimal]:
        price_rub = v.price_rub
        vat_rate = Decimal(str(self.tariffs.get("vat_rate", BASE_VAT)))

        ctp_cfg = self.tariffs.get("ctp")
        if not ctp_cfg:
            raise WrongParamException("ctp tariffs not configured")
        try:
            duty_rate = Decimal(str(ctp_cfg["duty_rate"]))
            min_cc_eur = ctp_cfg["min_per_cc_eur"]
        except KeyError as exc:
            raise WrongParamException(f"missing CTP tariff parameter: {exc}")
        min_duty_per_cc = Decimal(str(to_rub(min_cc_eur, "EUR")))
        duty_rub = _round2(
            max(price_rub * duty_rate, min_duty_per_cc * Decimal(v.engine_capacity))
        )

        excise = self.calculate_excise(v)
        vat = _round2((price_rub + duty_rub + excise) * vat_rate)

        clearance_fee = _round2(self.calculate_clearance_tax(v))
        decl_date = self.tariffs.get("util_date", date(2024, 1, 1))
        if isinstance(decl_date, str):
            decl_date = date.fromisoformat(decl_date)
        age_years = compute_actual_age_years(v.production_year, decl_date)
        coeff = Decimal(str(self.tariffs.get("ctp_util_coeff_base", 1.0)))
        util_fee = _round2(self._calculate_util_fee(v, age_years, decl_date, coeff))
        recycling_fee = self.calculate_recycling_fee(v)

        total_pay = _round2(
            duty_rub + excise + vat + clearance_fee + util_fee + recycling_fee
        )
        return {
            "mode": "CTP",
            "price_rub": _round2(price_rub),
            "duty_rub": duty_rub,
            "excise_rub": excise,
            "vat_rub": vat,
            "fee_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total_pay,
            "vehicle_price_rub": _round2(price_rub),
            "ctp_rub": _round2(price_rub + total_pay),
        }

    def _calc_etc(self, v: _Vehicle) -> Dict[str, Decimal]:
        vt = self._vehicle_tariffs(v)
        cfg = vt["age_groups"][v.age.value][v.engine_type.value]
        rate_per_cc = Decimal(str(to_rub(cfg["rate_per_cc"], "EUR")))
        min_duty = cfg.get("min_duty", 0)
        min_duty_rub = (
            Decimal(str(to_rub(min_duty, "EUR"))) if min_duty else Decimal("0")
        )
        duty_rub = _round2(
            max(rate_per_cc * Decimal(v.engine_capacity), min_duty_rub)
        )

        clearance_fee = _round2(self.calculate_clearance_tax(v))
        decl_date = self.tariffs.get("util_date", date(2024, 1, 1))
        if isinstance(decl_date, str):
            decl_date = date.fromisoformat(decl_date)
        age_years = compute_actual_age_years(v.production_year, decl_date)
        coeff = Decimal(str(self.tariffs.get("etc_util_coeff_base", 1.0)))
        util_fee = _round2(self._calculate_util_fee(v, age_years, decl_date, coeff))
        recycling_fee = self.calculate_recycling_fee(v)

        total_pay = _round2(duty_rub + clearance_fee + util_fee + recycling_fee)
        return {
            "mode": "ETC",
            "price_rub": _round2(v.price_rub),
            "duty_rub": duty_rub,
            "excise_rub": Decimal("0"),
            "vat_rub": Decimal("0"),
            "fee_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total_pay,
            "vehicle_price_rub": _round2(v.price_rub),
            "etc_rub": _round2(v.price_rub + total_pay),
        }

    def calculate_ctp(self) -> Dict[str, Decimal]:
        v = self._require_vehicle()
        res = self._calc_ctp(v)
        self._last_result = res
        return res

    def calculate_etc(self) -> Dict[str, Decimal]:
        v = self._require_vehicle()
        res = self._calc_etc(v)
        self._last_result = res
        return res

    def calculate_auto(self) -> Dict[str, Decimal]:
        v = self._require_vehicle()
        if v.owner_type is VehicleOwnerType.COMPANY:
            return self.calculate_ctp()
        etc = self._calc_etc(v)
        ctp = self._calc_ctp(v)
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
            [k, f"{float(v):,.2f}" if isinstance(v, (int, float, Decimal)) else v]
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

