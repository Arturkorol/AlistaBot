"""
Core Customs calculator for vehicle import (2025), pluggable and spec-aligned.

Designed for use in Telegram bot or CLI. Currency conversion is via injected FX
snapshot (RUB per unit) provided by the app (no I/O here).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Tuple

Money = Decimal


class ImporterType(str, Enum):
    INDIVIDUAL = "individual"
    LEGAL = "legal"


class VehicleCategory(str, Enum):
    M1 = "M1"
    OTHER = "OTHER"


class EngineType(str, Enum):
    ICE_GASOLINE = "ice_gasoline"
    ICE_DIESEL = "ice_diesel"
    HYBRID_PARALLEL = "hybrid_parallel"
    HYBRID_SERIES = "hybrid_series"
    EV = "ev"


class AgeCategory(str, Enum):
    LT3 = "lt3"
    Y3_5 = "y3_5"
    GT5 = "gt5"


@dataclass(frozen=True)
class FX:
    EUR: Money
    USD: Money = Money(0)
    JPY: Money = Money(0)
    CNY: Money = Money(0)

    def to_rub(self, amount: Money, currency: str) -> Money:
        cur = currency.upper()
        if cur == "RUB":
            return _q(amount)
        if cur == "EUR":
            return _q(amount * self.EUR)
        if cur == "USD":
            return _q(amount * self.USD)
        if cur == "JPY":
            return _q(amount * self.JPY)
        if cur == "CNY":
            return _q(amount * self.CNY)
        raise ValueError(f"Unsupported currency: {currency}")


@dataclass
class Input:
    importer: ImporterType
    vehicle_category: VehicleCategory
    engine_type: EngineType
    age_category: AgeCategory
    engine_cc: int
    horsepower: int
    customs_value_amount: Money
    customs_value_currency: str
    fx: FX


@dataclass
class Result:
    duty: Money
    excise: Money
    vat: Money
    util_fee: Money
    customs_fee: Money
    total: Money
    breakdown: Dict[str, Money]


TWOPL = Decimal("0.01")


def _q(x: Decimal | int | float) -> Money:
    return Money(x).quantize(TWOPL, rounding=ROUND_HALF_UP)


EESP_LT3_INTERVALS: List[Dict[str, Decimal | None]] = [
    {"max_eur": Decimal("8500"),   "advalorem": Decimal("0.54"), "min_eur_per_cc": Decimal("2.5")},
    {"max_eur": Decimal("16700"),  "advalorem": Decimal("0.48"), "min_eur_per_cc": Decimal("3.5")},
    {"max_eur": Decimal("42300"),  "advalorem": Decimal("0.48"), "min_eur_per_cc": Decimal("5.5")},
    {"max_eur": Decimal("84500"),  "advalorem": Decimal("0.48"), "min_eur_per_cc": Decimal("7.5")},
    {"max_eur": Decimal("169000"), "advalorem": Decimal("0.48"), "min_eur_per_cc": Decimal("15.0")},
    {"max_eur": None,               "advalorem": Decimal("0.48"), "min_eur_per_cc": Decimal("20.0")},
]

EESP_3TO5_EUR_PER_CC: List[Tuple[int | None, Decimal]] = [
    (1000, Decimal("1.5")),
    (1500, Decimal("1.7")),
    (1800, Decimal("2.5")),
    (2300, Decimal("2.7")),
    (3000, Decimal("3.0")),
    (None, Decimal("3.6")),
]

EESP_5PLUS_EUR_PER_CC: List[Tuple[int | None, Decimal]] = [
    (1000, Decimal("3.0")),
    (1500, Decimal("3.2")),
    (1800, Decimal("3.5")),
    (2300, Decimal("4.8")),
    (3000, Decimal("5.0")),
    (None, Decimal("5.7")),
]

EXCISE_PER_HP_BANDS: List[Tuple[int | None, Money]] = [
    (90, _q(0)),
    (150, _q(61)),
    (200, _q(583)),
    (300, _q(955)),
    (400, _q(1628)),
    (500, _q(1685)),
    (None, _q(1740)),
]

VAT_RATE = Decimal("0.20")

CUSTOMS_FEE_BRACKETS: List[Tuple[Money, Money]] = [
    (_q(200_000), _q(500)),
    (_q(450_000), _q(1_000)),
    (_q(1_200_000), _q(2_000)),
    (_q(2_700_000), _q(5_000)),
    (_q(5_000_000), _q(7_500)),
]
CUSTOMS_FEE_ABOVE_MAX = _q(20_000)

UTIL_BASE_BY_VEHICLE = {
    VehicleCategory.M1: _q(20_000),
    VehicleCategory.OTHER: _q(150_000),
}


class UtilCoeffProvider:
    def __call__(
        self,
        importer: ImporterType,
        vehicle_category: VehicleCategory,
        engine_type: EngineType,
        age_category: AgeCategory,
        engine_cc: int,
    ) -> Decimal:
        raise NotImplementedError


class DefaultUtilCoeffProvider(UtilCoeffProvider):
    def __call__(
        self,
        importer: ImporterType,
        vehicle_category: VehicleCategory,
        engine_type: EngineType,
        age_category: AgeCategory,
        engine_cc: int,
    ) -> Decimal:
        if engine_type in (EngineType.EV, EngineType.HYBRID_SERIES):
            if importer is ImporterType.INDIVIDUAL:
                return Decimal("0.17") if age_category == AgeCategory.LT3 else Decimal("0.26")
            else:
                return Decimal("33.37") if age_category == AgeCategory.LT3 else Decimal("58.7")
        raise ValueError("Utilization coefficient required; inject YAML-backed provider.")


@dataclass
class DutySchedule:
    ad_valorem_pct: Optional[Decimal] = None
    min_eur_per_cc: Optional[Decimal] = None
    per_cc_only_eur: Optional[Decimal] = None

    def compute(self, ts_rub: Money, cc: int, eur_rub: Money) -> Money:
        if self.per_cc_only_eur is not None:
            return _q(Decimal(cc) * self.per_cc_only_eur * eur_rub)
        if self.ad_valorem_pct is None:
            raise ValueError("DutySchedule misconfigured")
        ad_val = _q(ts_rub * self.ad_valorem_pct)
        if self.min_eur_per_cc is None:
            return ad_val
        percc = _q(Decimal(cc) * self.min_eur_per_cc * eur_rub)
        return ad_val if ad_val >= percc else percc


DEFAULT_LEGAL_DUTY_SCHEDULES: Dict[str, DutySchedule] = {
    "EV": DutySchedule(ad_valorem_pct=Decimal("0.0")),
}


class CustomsCalculator:
    def __init__(
        self,
        util_coeff_provider: Optional[UtilCoeffProvider] = None,
        legal_duty_resolver: Optional[Callable[[Input], DutySchedule]] = None,
    ):
        self.util_coeff_provider = util_coeff_provider or DefaultUtilCoeffProvider()
        self.legal_duty_resolver = legal_duty_resolver or self._default_legal_resolver

    def calculate(self, inp: Input) -> Result:
        ts_rub = inp.fx.to_rub(inp.customs_value_amount, inp.customs_value_currency)
        if inp.importer is ImporterType.INDIVIDUAL:
            duty = self._calc_eesp_duty(inp, ts_rub)
            excise = _q(0)
            vat = _q(0)
        else:
            duty = self._calc_legal_duty(inp, ts_rub)
            excise = self._calc_excise(inp)
            vat = self._calc_vat(ts_rub, duty, excise)
        util_fee = self._calc_util_fee(inp)
        customs_fee = self._calc_customs_ops_fee(ts_rub)
        total = _q(duty + excise + vat + util_fee + customs_fee)
        breakdown = {
            "customs_value_rub": ts_rub,
            "duty": duty,
            "excise": excise,
            "vat": vat,
            "util_fee": util_fee,
            "customs_ops_fee": customs_fee,
            "total": total,
        }
        return Result(duty, excise, vat, util_fee, customs_fee, total, breakdown)

    def _calc_eesp_duty(self, inp: Input, ts_rub: Money) -> Money:
        if inp.age_category == AgeCategory.LT3:
            ts_eur = _safe_div(ts_rub, inp.fx.EUR)
            row = _pick_lt3_bracket(ts_eur)
            ad_val_rub = _q(ts_rub * row["advalorem"])  # % of RUB value
            min_rub = _q(Decimal(inp.engine_cc) * row["min_eur_per_cc"] * inp.fx.EUR)
            return ad_val_rub if ad_val_rub >= min_rub else min_rub
        elif inp.age_category == AgeCategory.Y3_5:
            rate = _pick_per_cc_rate(inp.engine_cc, EESP_3TO5_EUR_PER_CC)
            return _q(Decimal(inp.engine_cc) * rate * inp.fx.EUR)
        else:
            rate = _pick_per_cc_rate(inp.engine_cc, EESP_5PLUS_EUR_PER_CC)
            return _q(Decimal(inp.engine_cc) * rate * inp.fx.EUR)

    def _calc_legal_duty(self, inp: Input, ts_rub: Money) -> Money:
        sched = self.legal_duty_resolver(inp)
        return sched.compute(ts_rub, inp.engine_cc, inp.fx.EUR)

    def _calc_excise(self, inp: Input) -> Money:
        if inp.engine_type == EngineType.EV:
            return _q(0)
        rate = _pick_excise_rate(inp.horsepower)
        return _q(rate * inp.horsepower)

    def _calc_vat(self, ts_rub: Money, duty: Money, excise: Money) -> Money:
        base = _q(ts_rub + duty + excise)
        return _q(base * VAT_RATE)

    def _calc_util_fee(self, inp: Input) -> Money:
        # Allow YAML provider to override base via optional base_rub(interface)
        base = None
        base_getter = getattr(self.util_coeff_provider, "base_rub", None)
        if callable(base_getter):
            try:
                base = base_getter(inp.vehicle_category)
            except Exception:
                base = None
        if base is None:
            base = UTIL_BASE_BY_VEHICLE.get(inp.vehicle_category)
        if base is None:
            raise ValueError("No util base for vehicle category")
        coeff = self.util_coeff_provider(inp.importer, inp.vehicle_category, inp.engine_type, inp.age_category, inp.engine_cc)
        return _q(base * coeff)

    def _calc_customs_ops_fee(self, ts_rub: Money) -> Money:
        for threshold, fee in CUSTOMS_FEE_BRACKETS:
            if ts_rub <= threshold:
                return fee
        return CUSTOMS_FEE_ABOVE_MAX

    @staticmethod
    def _default_legal_resolver(inp: Input) -> DutySchedule:
        if inp.engine_type == EngineType.EV:
            return DEFAULT_LEGAL_DUTY_SCHEDULES["EV"]
        raise ValueError("Provide legal duty resolver for non-EV")


def _pick_lt3_bracket(ts_eur: Money) -> Dict[str, Decimal | None]:
    for row in EESP_LT3_INTERVALS:
        mx = row["max_eur"]
        if mx is None or ts_eur <= mx:
            return row
    return EESP_LT3_INTERVALS[-1]


def _pick_per_cc_rate(cc: int, table: List[Tuple[int | None, Decimal]]) -> Decimal:
    for upper, rate in table:
        if upper is None or cc <= upper:
            return rate
    return table[-1][1]


def _pick_excise_rate(hp: int) -> Money:
    for upper, rate in EXCISE_PER_HP_BANDS:
        if upper is None or hp <= upper:
            return rate
    return EXCISE_PER_HP_BANDS[-1][1]


def _safe_div(a: Money, b: Money) -> Money:
    if b == 0:
        raise ZeroDivisionError("FX rate is zero")
    return _q(a / b)
