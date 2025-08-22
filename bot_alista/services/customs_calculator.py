from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from datetime import datetime
import yaml


class CustomsCalculator:
    """Perform customs calculations and expose ETC/CTP helpers.

    The class loads tariff configuration once and then can be instantiated
    multiple times.  Each call to :meth:`calculate_ctp` or
    :meth:`calculate_etc` resets vehicle specific state ensuring that results
    are isolated between invocations.
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
    # Initialization and state handling
    # ------------------------------------------------------------------

    def __init__(self, *, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None) -> None:
        self.eur_rate = eur_rate or 1.0
        self.tariffs = tariffs or self.get_tariffs()
        self._reset_state()

    def _reset_state(self) -> None:
        self.price_eur = 0.0
        self.engine_cc = 0
        self.year = 0
        self.car_type = ""
        self.power_hp = 0.0
        self.weight_kg = 0.0
        self._result: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Helpers ported from legacy modules
    # ------------------------------------------------------------------

    @staticmethod
    def _age_category(year: int) -> str:
        """Return age bucket used by tariff tables (ported from ``calculator``)."""
        age = datetime.now().year - year
        if age < 3:
            return "under_3"
        if age <= 5:
            return "3_5"
        return "over_5"

    @staticmethod
    def _clearance_fee_rub(customs_value_rub: float) -> float:
        """Tiered customs clearance fee (ported from ``tariff_engine``)."""
        v = float(customs_value_rub)
        if v <= 200_000:
            return 1_067.0
        if v <= 450_000:
            return 2_134.0
        if v <= 1_200_000:
            return 4_269.0
        if v <= 3_000_000:
            return 11_746.0
        if v <= 5_000_000:
            return 16_524.0
        if v <= 7_000_000:
            return 20_000.0
        return 30_000.0

    # ------------------------------------------------------------------
    # Core calculations
    # ------------------------------------------------------------------

    def _calculate_breakdown(self) -> Dict[str, float]:
        """Internal helper performing the actual math."""
        cat = self._age_category(self.year)
        tariffs = self.tariffs
        eur_rate = self.eur_rate

        price_eur = self.price_eur
        engine_cc = self.engine_cc
        power_hp = self.power_hp

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

        # VAT
        vat = 0.2 * (price_eur + duty + excise + util)

        # Processing fee uses tiered table in RUB then converted to EUR
        customs_value_rub = price_eur * eur_rate
        fee_rub = self._clearance_fee_rub(customs_value_rub)
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_ctp(
        self,
        *,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        power_hp: float = 0,
        weight_kg: float = 0,
    ) -> Dict[str, float]:
        """Calculate customs tax payments in euros.

        Returns a dictionary containing a detailed breakdown with a stable
        schema: ``duty_eur``, ``excise_eur``, ``util_eur``, ``vat_eur``,
        ``fee_eur`` and ``total_eur``.
        """

        self._reset_state()
        self.price_eur = price_eur
        self.engine_cc = engine_cc
        self.year = year
        self.car_type = car_type
        self.power_hp = power_hp
        self.weight_kg = weight_kg

        self._result = self._calculate_breakdown()
        return self._result.copy()

    def calculate_etc(
        self,
        *,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        power_hp: float = 0,
        weight_kg: float = 0,
    ) -> Dict[str, float]:
        """Return the estimated total cost including customs payments."""

        res = self.calculate_ctp(
            price_eur=price_eur,
            engine_cc=engine_cc,
            year=year,
            car_type=car_type,
            power_hp=power_hp,
            weight_kg=weight_kg,
        )
        etc = price_eur + res["total_eur"]
        res.update({"vehicle_price_eur": price_eur, "etc_eur": etc})
        return res
