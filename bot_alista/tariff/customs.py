"""Unified customs calculator supporting ETC and CTP modes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import yaml

from bot_alista.clearance_fee import calc_clearance_fee_rub


@dataclass
class Vehicle:
    age: str
    engine_capacity: int
    engine_type: str
    power: int
    price: float
    currency: str
    owner_type: str


class CustomsCalculator:
    """Calculator for Russian customs duties."""

    def __init__(self, config_path: str) -> None:
        with open(config_path, "r", encoding="utf-8") as fh:
            self.config = yaml.safe_load(fh)
        self.vehicle: Optional[Vehicle] = None

    # ------------------------------------------------------------------
    def set_vehicle(
        self,
        *,
        age: str,
        engine_capacity: int,
        engine_type: str,
        power: int,
        price: float,
        currency: str,
        owner_type: str,
    ) -> None:
        """Store vehicle parameters for subsequent calculations."""

        self.vehicle = Vehicle(
            age=age,
            engine_capacity=engine_capacity,
            engine_type=engine_type.lower(),
            power=power,
            price=price,
            currency=currency.upper(),
            owner_type=owner_type,
        )

    # ------------------------------------------------------------------
    # Helper methods
    def _ensure_vehicle(self) -> Vehicle:
        if not self.vehicle:
            raise ValueError("Vehicle details have not been set")
        return self.vehicle

    def _price_rub(self, price: float, currency: str) -> float:
        rate = self.config["currency_rates"][currency.upper()]
        return price * rate

    def _eur_to_rub(self) -> float:
        return self.config["currency_rates"]["EUR"]

    # ------------------------------------------------------------------
    # Calculation methods
    def calculate_etc(self) -> Dict[str, float]:
        v = self._ensure_vehicle()
        eur_to_rub = self._eur_to_rub()
        price_rub = self._price_rub(v.price, v.currency)
        tariffs = self.config["tariffs"]

        # Duty calculation
        overrides = tariffs.get("age_groups", {}).get("overrides", {})
        eng_override = overrides.get(v.age, {}).get(v.engine_type, {})
        rate_per_cc = eng_override.get("rate_per_cc", 0)
        min_duty = eng_override.get("min_duty", 0)
        duty_eur = max(rate_per_cc * v.engine_capacity, min_duty)
        duty = duty_eur * eur_to_rub

        # Fees
        clearance_fee = tariffs.get("base_clearance_fee", 0)
        util_fee = tariffs.get("base_util_fee", 0) * tariffs.get("etc_util_coeff_base", 1)

        # Recycling fee
        rec_cfg = tariffs.get("recycling_factors", {})
        default_factor = rec_cfg.get("default", {}).get(v.engine_type, 1)
        adj_factor = rec_cfg.get("adjustments", {}).get(v.age, {}).get(v.engine_type, 1)
        recycling_fee = tariffs.get("base_util_fee", 0) * default_factor * adj_factor

        total = duty + clearance_fee + util_fee + recycling_fee

        return {
            "price_rub": price_rub,
            "duty_rub": duty,
            "excise_rub": 0.0,
            "vat_rub": 0.0,
            "clearance_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": recycling_fee,
            "total_rub": total,
        }

    def calculate_ctp(self) -> Dict[str, float]:
        v = self._ensure_vehicle()
        eur_to_rub = self._eur_to_rub()
        price_rub = self._price_rub(v.price, v.currency)
        tariffs = self.config["tariffs"]

        # Duty
        duty_value = 0.2 * price_rub
        duty_specific = 0.44 * v.engine_capacity * eur_to_rub
        duty = max(duty_value, duty_specific)

        # Excise and VAT
        excise_rate = tariffs.get("excise_rates", {}).get(v.engine_type, 0)
        excise = v.power * excise_rate
        vat = 0.2 * (price_rub + duty + excise)

        clearance_fee = calc_clearance_fee_rub(
            price_rub, self.config.get("clearance_fee_ranges")
        )
        util_fee = tariffs.get("base_util_fee", 0) * tariffs.get("ctp_util_coeff_base", 1)

        total = duty + excise + vat + clearance_fee + util_fee

        return {
            "price_rub": price_rub,
            "duty_rub": duty,
            "excise_rub": excise,
            "vat_rub": vat,
            "clearance_rub": clearance_fee,
            "util_rub": util_fee,
            "recycling_rub": 0.0,
            "total_rub": total,
        }

    def calculate_auto(self) -> Dict[str, float]:
        v = self._ensure_vehicle()
        if v.age in {"new", "1-3", "3-5"}:
            return self.calculate_ctp()
        if v.age in {"5-7", "over_7"}:
            return self.calculate_etc()
        raise ValueError(f"Unsupported age group: {v.age}")


__all__ = ["CustomsCalculator"]
