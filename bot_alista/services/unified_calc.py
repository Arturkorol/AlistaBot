from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from bot_alista.services.core_calc import (
    CustomsCalculator as CoreCalculator,
    ImporterType as CoreImporter,
    VehicleCategory as CoreVehCat,
    EngineType as CoreEngine,
    AgeCategory as CoreAge,
    Input as CoreInput,
    FX as CoreFX,
)
from bot_alista.services.util_fee_provider import YAMLUtilCoeffProvider
from bot_alista.services.calc import CustomsCalculator as LegacyCalculator
from bot_alista.models.constants import KW_TO_HP


class UnifiedCalculator:
    """High-level calculator facade.

    - Individuals (personal use): uses core calculator (EESP tables).
    - Companies/commercial: uses YAML-driven legacy CTP logic.

    Produces a uniform breakdown compatible with existing formatting/pdf.
    """

    def __init__(self, settings: Any, rates: Dict[str, float]):
        self.settings = settings
        self.rates = rates
        self.cfg = settings.tariff_config

        # Core calc with YAML util-fee provider
        self._provider = YAMLUtilCoeffProvider(self.cfg)
        self._core = CoreCalculator(util_coeff_provider=self._provider)
        # Legacy calc for CTP
        self._legacy = LegacyCalculator(config=self.cfg, rates_snapshot=rates)

    def _map_engine(self, raw: str, subtype: str | None) -> CoreEngine:
        raw = (raw or "").lower()
        if raw == "gasoline":
            return CoreEngine.ICE_GASOLINE
        if raw == "diesel":
            return CoreEngine.ICE_DIESEL
        if raw == "electric":
            return CoreEngine.EV
        if raw == "hybrid":
            st = (subtype or "parallel").lower()
            return CoreEngine.HYBRID_SERIES if st == "series" else CoreEngine.HYBRID_PARALLEL
        return CoreEngine.ICE_GASOLINE

    def _map_age(self, key: str) -> CoreAge:
        if key in {"new", "1-3"}:
            return CoreAge.LT3
        if key == "3-5":
            return CoreAge.Y3_5
        return CoreAge.GT5

    def calculate(self, form: Dict[str, Any]) -> Dict[str, Any]:
        """Compute result using appropriate branch.

        form expects keys: age, engine, capacity, power, owner, currency, price,
        optional: power_unit, hybrid_subtype.
        """
        owner = (form.get("owner") or "").lower()
        importer = CoreImporter.INDIVIDUAL if owner == "individual" else CoreImporter.LEGAL

        currency = (form.get("currency") or "USD").upper()
        fx = CoreFX(
            EUR=Decimal(str(self.rates.get("EUR", 0))),
            USD=Decimal(str(self.rates.get("USD", 0))),
            JPY=Decimal(str(self.rates.get("JPY", 0))),
            CNY=Decimal(str(self.rates.get("CNY", 0))),
        )

        # Individual path -> core calc (EESP)
        if importer is CoreImporter.INDIVIDUAL:
            eng = self._map_engine(form.get("engine", ""), form.get("hybrid_subtype"))
            veh_cat = CoreVehCat.M1
            age_cat = self._map_age(str(form.get("age", "new")))
            # Power unit conversion (kW->HP) if needed
            power = int(form.get("power") or 0)
            if (form.get("power_unit") or "hp").lower() == "kw":
                try:
                    power = int(round(float(form.get("power", 0)) * KW_TO_HP))
                except Exception:
                    power = int(form.get("power") or 0)
            core_in = CoreInput(
                importer=importer,
                vehicle_category=veh_cat,
                engine_type=eng,
                age_category=age_cat,
                engine_cc=int(form.get("capacity") or 0),
                horsepower=power,
                customs_value_amount=Decimal(str(form.get("price", 0))),
                customs_value_currency=currency,
                fx=fx,
            )
            res = self._core.calculate(core_in)
            return {
                "customs_value_rub": res.breakdown["customs_value_rub"],
                "duty_rub": res.duty,
                "excise_rub": res.excise,
                "vat_rub": res.vat,
                "util_rub": res.util_fee,
                "clearance_fee_rub": res.customs_fee,
                "total_rub": (res.duty + res.excise + res.vat + res.customs_fee),
                "total_with_util_rub": res.total,
            }

        # Legal/commercial path -> legacy CTP
        self._legacy.set_vehicle_details(
            age=str(form.get("age") or "new"),
            engine_capacity=int(form.get("capacity") or 0),
            engine_type=str(form.get("engine") or "gasoline"),
            power=int(form.get("power") or 0),
            price=float(form.get("price") or 0.0),
            owner_type=str(form.get("owner") or "company"),
            currency=currency,
            power_unit=str(form.get("power_unit") or "hp"),
            hybrid_subtype=str(form.get("hybrid_subtype") or ""),
        )
        out = self._legacy.calculate_ctp()
        # Map to uniform breakdown with Decimals
        to_dec = lambda x: Decimal(str(x))
        price_rub = self._legacy.convert_to_local_currency(float(form.get("price") or 0.0), currency)
        return {
            "customs_value_rub": Decimal(str(price_rub)),
            "duty_rub": to_dec(out.get("Duty (RUB)", 0)),
            "excise_rub": to_dec(out.get("Excise (RUB)", 0)),
            "vat_rub": to_dec(out.get("VAT (RUB)", 0)),
            "util_rub": to_dec(out.get("Util Fee (RUB)", 0)),
            "clearance_fee_rub": to_dec(out.get("Clearance Fee (RUB)", 0)),
            "total_rub": to_dec(out.get("Duty (RUB)", 0)) + to_dec(out.get("Excise (RUB)", 0)) + to_dec(out.get("VAT (RUB)", 0)) + to_dec(out.get("Clearance Fee (RUB)", 0)),
            "total_with_util_rub": to_dec(out.get("Total Pay (RUB)", 0)),
        }
