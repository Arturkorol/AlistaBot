from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from datetime import datetime
import yaml


class CustomsCalculator:
    """Utility loader for customs tariff configuration.

    The class lazily reads :mod:`config/tariffs.yaml` once and caches the
    resulting dictionary. This provides a single source of truth for all customs
    related calculations within the bot.
    """

    _tariffs: Dict[str, Any] | None = None

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """Load tariff configuration from the bundled YAML file."""
        if cls._tariffs is None:
            config_path = (
                Path(__file__).resolve().parents[2]
                / "config"
                / "tariffs.yaml"
            )
            with open(config_path, "r", encoding="utf-8") as fh:
                cls._tariffs = yaml.safe_load(fh)
        return cls._tariffs

    @classmethod
    def get_tariffs(cls) -> Dict[str, Any]:
        """Return cached tariff data."""
        return cls._load_config()

    # ------------------------------------------------------------------
    # Convenience calculation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _age_category(year: int) -> str:
        age = datetime.now().year - year
        if age < 3:
            return "under_3"
        if age <= 5:
            return "3_5"
        return "over_5"

    @staticmethod
    def _pick_rate(table, value):
        for limit, rate in table:
            if value <= limit:
                return rate
        return table[-1][1]

    @classmethod
    def calculate_customs(
        cls,
        *,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
        tariffs: Dict[str, Any] | None = None,
    ) -> Dict[str, float]:
        """Return detailed customs calculation using simple tariff rules."""
        tariffs = tariffs or cls.get_tariffs()
        eur_rate = eur_rate or 1.0
        cat = cls._age_category(year)

        fl_duty = tariffs["duty"]["fl"]
        if cat == "under_3":
            rule = cls._pick_rate(fl_duty["under_3"], engine_cc)
            duty = max(price_eur * rule["pct"], engine_cc * rule["min"])
        else:
            table_key = cat if cat in fl_duty else "over_5"
            rate = cls._pick_rate(fl_duty[table_key], engine_cc)
            duty = engine_cc * rate

        excise = 0.0
        if power_hp:
            per_hp_rub = cls._pick_rate(tariffs["excise"]["hp"], power_hp)
            excise = power_hp * (per_hp_rub / eur_rate)

        util_key = "under_3" if cat == "under_3" else "over_3"
        util = tariffs["utilization"]["fl"][util_key]

        vat = 0.2 * (price_eur + duty + excise + util)
        fee_rub = cls._pick_rate(tariffs["processing_fee"], price_eur * eur_rate)
        fee = fee_rub / eur_rate

        total = duty + excise + util + vat + fee
        return {
            "duty_eur": duty,
            "excise_eur": excise,
            "util_eur": util,
            "vat_eur": vat,
            "fee_eur": fee,
            "total_eur": total,
        }

    @classmethod
    def calculate_ctp(
        cls,
        *,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
        tariffs: Dict[str, Any] | None = None,
    ) -> float:
        """Return customs tax payments in euros for the given vehicle.

        This is a thin wrapper around :meth:`calculate_customs` that extracts
        the ``total_eur`` field from the result.  ``tariffs`` may be supplied to
        use custom tariff data; when omitted the bundled sample rates are used.
        """

        res = cls.calculate_customs(
            price_eur=price_eur,
            engine_cc=engine_cc,
            year=year,
            car_type=car_type,
            power_hp=power_hp,
            weight_kg=weight_kg,
            eur_rate=eur_rate,
            tariffs=tariffs,
        )
        return res["total_eur"]

    @classmethod
    def calculate_etc(
        cls,
        *,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
        tariffs: Dict[str, Any] | None = None,
    ) -> float:
        """Return the estimated total cost including customs payments.

        ``ETC`` equals the vehicle price plus customs tax payments calculated by
        :meth:`calculate_ctp`.
        """

        ctp = cls.calculate_ctp(
            price_eur=price_eur,
            engine_cc=engine_cc,
            year=year,
            car_type=car_type,
            power_hp=power_hp,
            weight_kg=weight_kg,
            eur_rate=eur_rate,
            tariffs=tariffs,
        )
        return price_eur + ctp
