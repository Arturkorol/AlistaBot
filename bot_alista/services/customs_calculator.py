from __future__ import annotations

"""Stateful customs calculator with currency conversion support."""

from pathlib import Path
from typing import Any, Dict
import yaml

from .currency import to_rub


class CustomsCalculator:
    """Calculate customs payments for vehicles.

    The calculator loads tariff configuration from ``external/tks_api_official``
    and stores vehicle parameters after :meth:`set_vehicle_details`. Subsequent
    calls to :meth:`calculate_ctp` or :meth:`calculate_etc` use this stored
    state, allowing incremental configuration of vehicle attributes.
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        eur_rate: float = 1.0,
        tariffs: Dict[str, Any] | None = None,
    ) -> None:
        if tariffs is not None:
            self.tariffs = tariffs
        else:
            if config_path is None:
                config_path = (
                    Path(__file__).resolve().parents[2]
                    / "external"
                    / "tks_api_official"
                    / "config.yaml"
                )
            with open(config_path, "r", encoding="utf-8") as fh:
                self.tariffs = yaml.safe_load(fh)
        self.eur_rate = eur_rate
        self._vehicle: Dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Vehicle state
    # ------------------------------------------------------------------
    def set_vehicle_details(
        self,
        *,
        age: str,
        engine_capacity: int,
        engine_type: str,
        power: int,
        price: float,
        owner_type: str,
        currency: str = "EUR",
    ) -> None:
        """Persist vehicle parameters for subsequent calculations."""

        age_groups = self.tariffs.get("age_groups", {})
        if age not in age_groups:
            raise ValueError("Unsupported age group")
        if engine_capacity < 800 or engine_capacity > 8000:
            raise ValueError("engine_capacity out of range")

        price_rub = to_rub(price, currency)
        price_eur = price_rub / self.eur_rate

        self._vehicle = {
            "age": age,
            "engine_capacity": int(engine_capacity),
            "engine_type": engine_type,
            "power": int(power),
            "price_eur": float(price_eur),
            "owner_type": owner_type,
            "currency": currency,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_vehicle(self) -> Dict[str, Any]:
        if not self._vehicle:
            raise ValueError("Vehicle details not set")
        return self._vehicle

    def _recycling_factor(self, age: str, engine_type: str) -> float:
        rf = self.tariffs["recycling_factors"]["default"][engine_type]
        adj = (
            self.tariffs["recycling_factors"].get("adjustments", {})
            .get(age, {})
            .get(engine_type)
        )
        return adj if adj is not None else rf

    def _duty(self, age: str, engine_type: str, engine_cc: int) -> float:
        cfg = self.tariffs["age_groups"][age][engine_type]
        rate = cfg.get("rate_per_cc", 0)
        min_duty = cfg.get("min_duty", 0)
        return max(rate * engine_cc, min_duty)

    def _excise(self, engine_type: str, power: int) -> float:
        rate_rub = self.tariffs["excise_rates"].get(engine_type, 0)
        return (rate_rub * power) / self.eur_rate

    def _util(self, age: str, engine_type: str, coeff_base: float) -> float:
        base_rub = self.tariffs["base_util_fee"]
        factor = self._recycling_factor(age, engine_type)
        return (base_rub * coeff_base * factor) / self.eur_rate

    def _fee(self) -> float:
        fee_rub = self.tariffs["base_clearance_fee"]
        return fee_rub / self.eur_rate

    def _calculate(self, coeff_base: float) -> Dict[str, float]:
        v = self._require_vehicle()
        age = v["age"]
        engine_type = v["engine_type"]
        engine_cc = v["engine_capacity"]
        power = v["power"]
        price_eur = v["price_eur"]

        duty = self._duty(age, engine_type, engine_cc)
        excise = self._excise(engine_type, power)
        util = self._util(age, engine_type, coeff_base)
        fee = self._fee()
        vat_rate = self.tariffs.get("vat_rate", 0)
        vat = vat_rate * (price_eur + duty + excise + util + fee)
        total = duty + excise + util + vat + fee
        return {
            "price_eur": price_eur,
            "eur_rate": self.eur_rate,
            "duty_eur": duty,
            "excise_eur": excise,
            "util_eur": util,
            "vat_eur": vat,
            "fee_eur": fee,
            "total_eur": total,
        }

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
        res["etc_eur"] = res["price_eur"] + res["total_eur"]
        return res
