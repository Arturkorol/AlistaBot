"""Official TKS customs calculator.

This module provides a `CustomsCalculator` class that loads tariff data from a
YAML configuration file and exposes high level helpers for calculating customs
payments.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import time
import requests
import xml.etree.ElementTree as ET
import yaml


@dataclass
class CalculationResult:
    price_eur: float
    engine: int
    power_hp: float
    year: int
    age: int
    eur_rate: float
    duty_eur: float
    excise_eur: float
    vat_eur: float
    util_eur: float
    fee_eur: float
    total_eur: float
    total_rub: float


class CustomsCalculator:
    """Calculator for customs payments based on tariff configuration."""

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = (
            Path(config_path) if config_path else Path(__file__).with_name("config.yaml")
        )
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.tariffs: Dict[str, Any] = yaml.safe_load(f)
        self._cached_rate: float | None = None
        self._cached_date: datetime.date | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_cbr_eur_rate(self, retries: int = 3, delay: int = 2) -> float | None:
        """Fetch daily EUR rate from the Russian Central Bank."""
        if self._cached_rate and self._cached_date == datetime.today().date():
            return self._cached_rate

        url = "https://www.cbr.ru/scripts/XML_daily.asp"
        for attempt in range(1, retries + 1):
            try:
                r = requests.get(url, timeout=5)
                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}")
                r.encoding = "windows-1251"
                tree = ET.fromstring(r.text)
                for valute in tree.findall("Valute"):
                    if valute.find("CharCode").text == "EUR":
                        eur_rate = float(valute.find("Value").text.replace(",", "."))
                        self._cached_rate = eur_rate
                        self._cached_date = datetime.today().date()
                        return eur_rate
            except Exception:
                if attempt < retries:
                    time.sleep(delay)
        return None

    def _calculate(
        self,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        *,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
    ) -> CalculationResult:
        """Core calculation routine used by public helpers."""
        current_year = datetime.now().year
        age = current_year - year

        tariffs = self.tariffs
        duty_tables = tariffs["duty"]
        under_3 = duty_tables.get("under_3", {"per_cc": 2.5, "price_percent": 0.48})
        rates_3_5 = duty_tables.get("3_5", [])
        rates_5_plus = duty_tables.get("over_5", [])

        duty = 0.0
        excise_rub = 0.0
        utilization_fee = 0.0

        if car_type.lower() in ["бензин", "дизель"]:
            if age < 3:
                duty = max(
                    price_eur * under_3.get("price_percent", 0.48),
                    engine_cc * under_3.get("per_cc", 2.5),
                )
            elif 3 <= age <= 5:
                rate = next(rate for limit, rate in rates_3_5 if engine_cc <= limit)
                duty = engine_cc * rate
            else:
                rate = next(rate for limit, rate in rates_5_plus if engine_cc <= limit)
                duty = engine_cc * rate
            if engine_cc > 3000:
                excise_rub = power_hp * tariffs["excise"].get("over_3000_hp_rub", 0)
        elif car_type.lower() == "гибрид":
            if age < 3:
                duty = max(
                    price_eur * under_3.get("price_percent", 0.48),
                    engine_cc * under_3.get("per_cc", 2.5),
                ) * 0.5
            elif 3 <= age <= 5:
                rate = next(rate for limit, rate in rates_3_5 if engine_cc <= limit) * 0.5
                duty = engine_cc * rate
            else:
                rate = next(rate for limit, rate in rates_5_plus if engine_cc <= limit) * 0.5
                duty = engine_cc * rate
        elif car_type.lower() == "электро":
            duty = 0.0
            excise_rub = 0.0

        util_table = tariffs["utilization"]
        utilization_fee_rub = (
            util_table["age_over_3"] if age > 3 else util_table["age_under_3"]
        )

        if eur_rate is None:
            eur_rate = self._get_cbr_eur_rate()
        if eur_rate is None:
            eur_rate = 100.0

        utilization_fee = utilization_fee_rub / eur_rate
        excise = excise_rub / eur_rate

        vat = (price_eur + duty + excise + utilization_fee) * 0.20
        fee = tariffs.get("processing_fee", 5)
        total_eur = duty + excise + vat + utilization_fee + fee
        total_rub = total_eur * eur_rate

        return CalculationResult(
            price_eur=round(price_eur, 2),
            engine=engine_cc,
            power_hp=power_hp,
            year=year,
            age=age,
            eur_rate=round(eur_rate, 2),
            duty_eur=round(duty, 2),
            excise_eur=round(excise, 2),
            vat_eur=round(vat, 2),
            util_eur=round(utilization_fee, 2),
            fee_eur=fee,
            total_eur=round(total_eur, 2),
            total_rub=round(total_rub, 2),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def calculate_etc(
        self,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        *,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
    ) -> Dict[str, float]:
        """Calculate ETC payments (general customs duties)."""
        res = self._calculate(
            price_eur,
            engine_cc,
            year,
            car_type,
            power_hp=power_hp,
            weight_kg=weight_kg,
            eur_rate=eur_rate,
        )
        return res.__dict__

    def calculate_ctp(
        self,
        price_eur: float,
        engine_cc: int,
        year: int,
        car_type: str,
        *,
        power_hp: float = 0,
        weight_kg: float = 0,
        eur_rate: float | None = None,
    ) -> Dict[str, float]:
        """Alias for calculating CTP payments (same as ETC for now)."""
        return self.calculate_etc(
            price_eur,
            engine_cc,
            year,
            car_type,
            power_hp=power_hp,
            weight_kg=weight_kg,
            eur_rate=eur_rate,
        )
