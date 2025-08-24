"""Stateful customs calculator with currency conversion support.

This module provides a light‑weight implementation of the customs
calculation engine that mimics the behaviour of the original project
while keeping the public API stable.  It converts input prices to EUR
using :class:`CurrencyConverter`, calculates all fees in euros and then
returns both EUR and RUB values (using the provided ``eur_rate``).

The code is intentionally self contained so that tests can run without
the optional ``tks_api_official`` dependency shipped with the real
project.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
try:  # pragma: no cover - handle environments without the real package
    from currency_converter import CurrencyConverter  # type: ignore
except Exception:  # pragma: no cover
    from currency_converter_free import CurrencyConverter  # type: ignore
from tabulate import tabulate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations and Exceptions
# ---------------------------------------------------------------------------


class EnginePowerUnit(str, Enum):
    """Units for engine power."""

    HP = "hp"
    KW = "kw"


class EngineType(str, Enum):
    """Supported engine types."""

    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class VehicleAge(str, Enum):
    """Age groups for vehicles as used in the tariff table."""

    NEW = "new"
    AGE_1_3 = "1-3"
    AGE_3_5 = "3-5"
    AGE_5_7 = "5-7"
    OVER_7 = "over_7"


class VehicleOwnerType(str, Enum):
    """Vehicle ownership categories."""

    INDIVIDUAL = "individual"
    COMPANY = "company"


class WrongParamException(ValueError):
    """Raised when user supplied parameters are not supported."""


# ---------------------------------------------------------------------------
# Helper dataclass for vehicle details
# ---------------------------------------------------------------------------


@dataclass
class _Vehicle:
    age: VehicleAge
    engine_capacity: int
    engine_type: EngineType
    power_hp: int
    price_eur: float
    owner_type: VehicleOwnerType
    currency: str


# ---------------------------------------------------------------------------
# Customs calculator implementation
# ---------------------------------------------------------------------------


class CustomsCalculator:
    """Calculate customs payments for vehicles.

    Parameters are first stored using :meth:`set_vehicle_details` and then
    used by :meth:`calculate_ctp` or :meth:`calculate_etc`.  Results include
    both EUR and RUB values.  ``eur_rate`` represents the EUR/RUB exchange
    rate and defaults to ``1.0`` so values in EUR and RUB are identical.
    """

    # Fallback conversion rates used if ``CurrencyConverter`` has no data
    # for the requested currency.  These match the values used by the
    # existing ``services.currency`` helper for deterministic tests.
    _FALLBACK_RATES = {"USD": 0.9, "KRW": 0.0007, "RUB": 0.01}

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        eur_rate: float = 1.0,
        tariffs: Optional[Dict[str, Any]] = None,
        converter: Optional[CurrencyConverter] = None,
    ) -> None:
        self.tariffs = tariffs or self.get_tariffs(config_path)
        self.eur_rate = eur_rate
        self.converter = converter or CurrencyConverter()
        self._vehicle: Optional[_Vehicle] = None
        self._last_result: Dict[str, float] | None = None

    # ------------------------------------------------------------------
    # Tariff loading
    # ------------------------------------------------------------------
    @staticmethod
    def get_tariffs(path: str | Path | None = None) -> Dict[str, Any]:
        """Return tariff configuration from ``config.yaml``."""

        if path is None:
            path = (
                Path(__file__).resolve().parents[2]
                / "external"
                / "tks_api_official"
                / "config.yaml"
            )
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    # ------------------------------------------------------------------
    # Vehicle state
    # ------------------------------------------------------------------
    def set_vehicle_details(
        self,
        *,
        age: str | VehicleAge,
        engine_capacity: int,
        engine_type: str | EngineType,
        power: int,
        price: float,
        owner_type: str | VehicleOwnerType,
        currency: str = "EUR",
        power_unit: EnginePowerUnit | str = EnginePowerUnit.HP,
    ) -> None:
        """Persist vehicle parameters for subsequent calculations."""

        try:
            age_enum = age if isinstance(age, VehicleAge) else VehicleAge(age)
            engine_enum = (
                engine_type
                if isinstance(engine_type, EngineType)
                else EngineType(engine_type)
            )
            owner_enum = (
                owner_type
                if isinstance(owner_type, VehicleOwnerType)
                else VehicleOwnerType(owner_type)
            )
            unit_enum = (
                power_unit
                if isinstance(power_unit, EnginePowerUnit)
                else EnginePowerUnit(power_unit)
            )
        except ValueError as exc:  # pragma: no cover - defensive
            raise WrongParamException(str(exc)) from exc

        if engine_capacity < 800 or engine_capacity > 8000:
            raise WrongParamException("engine_capacity out of range")

        # Convert power to horsepower if supplied in kW
        power_hp = power if unit_enum is EnginePowerUnit.HP else int(round(power * 1.35962))

        price_eur = self._to_eur(price, currency)

        self._vehicle = _Vehicle(
            age=age_enum,
            engine_capacity=int(engine_capacity),
            engine_type=engine_enum,
            power_hp=int(power_hp),
            price_eur=float(price_eur),
            owner_type=owner_enum,
            currency=currency.upper(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _to_eur(self, amount: float, currency: str) -> float:
        """Convert ``amount`` from ``currency`` to EUR using ``CurrencyConverter``."""

        code = currency.upper()
        if code == "EUR":
            return float(amount)
        try:
            return float(self.converter.convert(amount, code, "EUR"))
        except Exception:
            rate = self._FALLBACK_RATES.get(code)
            if rate is None:
                raise WrongParamException(f"Unsupported currency: {currency}")
            return float(amount) * rate

    def _require_vehicle(self) -> _Vehicle:
        if not self._vehicle:
            raise WrongParamException("Vehicle details not set")
        return self._vehicle

    def _recycling_factor(self, age: VehicleAge, engine_type: EngineType) -> float:
        rf = self.tariffs["recycling_factors"]["default"][engine_type.value]
        adj = (
            self.tariffs["recycling_factors"].get("adjustments", {})
            .get(age.value, {})
            .get(engine_type.value)
        )
        return adj if adj is not None else rf

    def _duty(self, age: VehicleAge, engine_type: EngineType, engine_cc: int) -> float:
        cfg = self.tariffs["age_groups"][age.value][engine_type.value]
        rate_rub = cfg.get("rate_per_cc", 0)
        min_duty_rub = cfg.get("min_duty", 0)
        duty_rub = max(rate_rub * engine_cc, min_duty_rub)
        # Tariff values are expressed in RUB; convert to EUR for calculations
        return float(duty_rub) / self.eur_rate

    def _excise(self, engine_type: EngineType, power: int) -> float:
        rate_rub = self.tariffs["excise_rates"].get(engine_type.value, 0)
        return float(rate_rub * power) / self.eur_rate

    def _util(self, age: VehicleAge, engine_type: EngineType, coeff_base: float) -> float:
        base_rub = self.tariffs["base_util_fee"]
        factor = self._recycling_factor(age, engine_type)
        return float(base_rub * coeff_base * factor) / self.eur_rate

    def _fee(self) -> float:
        fee_rub = self.tariffs["base_clearance_fee"]
        return float(fee_rub) / self.eur_rate

    def _calculate(self, coeff_base: float) -> Dict[str, float]:
        v = self._require_vehicle()
        age = v.age
        engine_type = v.engine_type
        engine_cc = v.engine_capacity
        power = v.power_hp
        price_eur = v.price_eur

        duty_eur = self._duty(age, engine_type, engine_cc)
        excise_eur = self._excise(engine_type, power)
        util_eur = self._util(age, engine_type, coeff_base)
        fee_eur = self._fee()

        vat_rate = self.tariffs.get("vat_rate", 0)
        vat_eur = vat_rate * (price_eur + duty_eur + excise_eur + util_eur + fee_eur)
        total_eur = duty_eur + excise_eur + util_eur + vat_eur + fee_eur

        result = {
            "price_eur": price_eur,
            "eur_rate": self.eur_rate,
            "duty_eur": duty_eur,
            "excise_eur": excise_eur,
            "util_eur": util_eur,
            "vat_eur": vat_eur,
            "fee_eur": fee_eur,
            "total_eur": total_eur,
        }

        # Derive RUB values for backwards compatibility and debugging
        for key in list(result.keys()):
            if key.endswith("_eur") or key == "price_eur":
                rub_key = key.replace("_eur", "_rub").replace("price_eur", "price_rub")
                result[rub_key] = result[key] * self.eur_rate

        result["total_rub"] = result["total_eur"] * self.eur_rate
        self._last_result = result
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def calculate_ctp(self) -> Dict[str, float]:
        """Return customs payments using CTP method."""

        coeff = self.tariffs.get("ctp_util_coeff_base", 1.0)
        return self._calculate(coeff)

    def calculate_etc(self) -> Dict[str, float]:
        """Return customs payments including purchase price (ETC)."""

        coeff = self.tariffs.get("etc_util_coeff_base", 1.0)
        res = self._calculate(coeff)
        res["vehicle_price_eur"] = res["price_eur"]
        res["vehicle_price_rub"] = res["price_rub"]
        res["etc_eur"] = res["price_eur"] + res["total_eur"]
        res["etc_rub"] = res["price_rub"] + res["total_rub"]
        self._last_result = res
        return res

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------
    def print_table(self, data: Optional[Dict[str, float]] = None) -> str:
        """Return a tabulated string of the calculation result.

        If ``data`` is ``None`` the last calculation result is used.  The
        function logs the table at ``DEBUG`` level and also returns it so tests
        can assert on the formatted string if required.
        """

        result = data or self._last_result or {}
        table = tabulate(sorted(result.items()), headers=["key", "value"], floatfmt=".2f")
        logger.debug("\n%s", table)
        return table


__all__ = [
    "CustomsCalculator",
    "EnginePowerUnit",
    "EngineType",
    "VehicleAge",
    "VehicleOwnerType",
    "WrongParamException",
]

