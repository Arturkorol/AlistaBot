"""Customs duties calculator for vehicle imports into Russia.

This module implements two calculation modes corresponding to
ETC (Unified Rate) and CTP (Comprehensive Customs Payment).
It mirrors the simplified logic of the Russian TKS system and
can be easily integrated with the Telegram bot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import yaml
from currency_converter_free import CurrencyConverter

# Clearance fee ladder used for CTP calculations.
CUSTOMS_CLEARANCE_TAX_RANGES = [
    (200_000, 775),
    (450_000, 1_550),
    (1_200_000, 3_100),
    (2_700_000, 8_530),
    (4_200_000, 12_000),
    (5_500_000, 15_500),
    (7_000_000, 20_000),
    (8_000_000, 23_000),
    (9_000_000, 25_000),
    (10_000_000, 27_000),
    (float("inf"), 30_000),
]


@dataclass
class VehicleDetails:
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
        self.converter = CurrencyConverter()
        self.vehicle: Optional[VehicleDetails] = None

    # ------------------------------------------------------------------
    def set_vehicle_details(
        self,
        age: str,
        engine_capacity: int,
        engine_type: str,
        power: int,
        price: float,
        currency: str,
        owner_type: str,
    ) -> None:
        """Store vehicle parameters for subsequent calculations."""

        self.vehicle = VehicleDetails(
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
    def _ensure_vehicle(self) -> VehicleDetails:
        if not self.vehicle:
            raise ValueError("Vehicle details have not been set")
        return self.vehicle

    def _price_rub(self, price: float, currency: str) -> float:
        return float(self.converter.convert(price, currency, "RUB"))

    def _eur_to_rub(self) -> float:
        return float(self.converter.convert(1, "EUR", "RUB"))

    def _ctp_clearance_fee(self, price_rub: float) -> float:
        for limit, fee in CUSTOMS_CLEARANCE_TAX_RANGES:
            if price_rub <= limit:
                return fee
        return CUSTOMS_CLEARANCE_TAX_RANGES[-1][1]

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
            "Mode": "ETC",
            "Price (RUB)": price_rub,
            "Duty (RUB)": duty,
            "Excise (RUB)": 0.0,
            "VAT (RUB)": 0.0,
            "Clearance Fee (RUB)": clearance_fee,
            "Util Fee (RUB)": util_fee,
            "Recycling Fee (RUB)": recycling_fee,
            "Total Pay (RUB)": total,
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

        clearance_fee = self._ctp_clearance_fee(price_rub)
        util_fee = tariffs.get("base_util_fee", 0) * tariffs.get("ctp_util_coeff_base", 1)

        total = duty + excise + vat + clearance_fee + util_fee

        return {
            "Mode": "CTP",
            "Price (RUB)": price_rub,
            "Duty (RUB)": duty,
            "Excise (RUB)": excise,
            "VAT (RUB)": vat,
            "Clearance Fee (RUB)": clearance_fee,
            "Util Fee (RUB)": util_fee,
            "Recycling Fee (RUB)": 0.0,
            "Total Pay (RUB)": total,
        }

    def auto_calculate(self) -> Dict[str, float]:
        v = self._ensure_vehicle()
        if v.age in {"new", "1-3", "3-5"}:
            return self.calculate_ctp()
        if v.age in {"5-7", "over_7"}:
            return self.calculate_etc()
        raise ValueError(f"Unsupported age group: {v.age}")
