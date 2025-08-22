from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
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

        This is a thin wrapper around :func:`calculate_customs` that extracts
        the ``total_eur`` field from the result.  ``tariffs`` may be supplied to
        use custom tariff data; when omitted the bundled sample rates are used.
        """

        from .customs import calculate_customs  # Lazy import to avoid cycles

        res = calculate_customs(
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
