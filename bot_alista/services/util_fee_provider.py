from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any

from bot_alista.services.core_calc import (
    UtilCoeffProvider,
    ImporterType,
    VehicleCategory,
    EngineType,
    AgeCategory,
)


class YAMLUtilCoeffProvider(UtilCoeffProvider):
    """Utilization fee coefficients from config tariffs.util_fee_1291."""

    def __init__(self, config: Dict[str, Any]):
        self.cfg = ((config or {}).get("tariffs") or {}).get("util_fee_1291") or {}

    def base_rub(self, vehicle_category: VehicleCategory) -> Decimal:
        # For now, one base for the given category; extend if YAML adds per-category bases
        return Decimal(str(self.cfg.get("base_rub", 20000)))

    def __call__(
        self,
        importer: ImporterType,
        vehicle_category: VehicleCategory,
        engine_type: EngineType,
        age_category: AgeCategory,
        engine_cc: int,
    ) -> Decimal:
        base_rub = Decimal(str(self.cfg.get("base_rub", 20000)))
        # Return coefficient only; core calculator multiplies by base
        if importer is ImporterType.INDIVIDUAL:
            pers = self.cfg.get("personal_use", {})
            key = "lt3y" if age_category == AgeCategory.LT3 else "ge3y"
            bucket = pers.get(key, {})
            coeff = bucket.get("coefficient")
            if coeff is None:
                # fallback via engine-types (values equal per spec)
                et = (pers.get("engine_types") or {})
                branch = et.get("ev_or_hybrid_series") or et.get("ice_or_hybrid_parallel") or {}
                coeff = (branch.get(key) or {}).get("coefficient", 0)
            return Decimal(str(coeff))

        # Commercial
        comm = self.cfg.get("commercial", {})
        key = "lt3y" if age_category == AgeCategory.LT3 else "ge3y"
        et = (comm.get("engine_types") or {})
        if engine_type == EngineType.EV and "ev" in et:
            coeff = (et["ev"].get(key) or {}).get("coefficient", 0)
            return Decimal(str(coeff))
        if engine_type == EngineType.HYBRID_SERIES and "hybrid_series" in et:
            coeff = (et["hybrid_series"].get(key) or {}).get("coefficient", 0)
            return Decimal(str(coeff))
        # Otherwise, use by_engine_cc ladder
        bycc = ((comm.get("by_engine_cc") or {}).get(key)) or []
        selected = None
        for row in bycc:
            to_cc = row.get("to_cc")
            if to_cc is None or engine_cc <= int(to_cc):
                selected = row
                break
        if selected is None and bycc:
            selected = bycc[-1]
        coeff = (selected or {}).get("coefficient", 0)
        return Decimal(str(coeff))
