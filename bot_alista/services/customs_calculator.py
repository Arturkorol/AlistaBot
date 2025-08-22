from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from datetime import datetime
import yaml


class CustomsCalculator:
    """Utility loader for customs tariff configuration.

    The class lazily reads :mod:`external/tks_api_official/config.yaml` once and
    caches the resulting dictionary.  This provides a single source of truth for
    all customs related calculations within the bot.
    """

    _tariffs: Dict[str, Any] | None = None

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """Load tariff configuration from the bundled YAML file."""
        if cls._tariffs is None:
            config_path = (
                Path(__file__).resolve().parents[2]
                / "external"
                / "tks_api_official"
                / "config.yaml"
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

        # Duty
        if cat == "under_3":
            cfg = tariffs["duty"]["under_3"]
            duty = max(price_eur * cfg["price_percent"], engine_cc * cfg["per_cc"])
        else:
            table = tariffs["duty"][cat]
            rate = next(r for limit, r in table if engine_cc <= limit)
            duty = engine_cc * rate

        # Excise (only when engine volume over 3000 cc)
        excise = 0.0
        if engine_cc > 3000:
            exc_cfg = tariffs.get("excise", {})
            per_hp = exc_cfg.get("over_3000_hp_rub", 0.0) / eur_rate
            excise = power_hp * per_hp

        # Utilization fee
        util_key = "age_under_3" if cat == "under_3" else "age_over_3"
        util = tariffs.get("utilization", {}).get(util_key, 0.0)

        # VAT is 20% of price + duty + excise + utilization
        vat = 0.2 * (price_eur + duty + excise + util)
        fee = tariffs.get("processing_fee", 0.0)

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
