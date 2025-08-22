from __future__ import annotations

"""Utility fee calculation for U.S. vehicles.

This module provides configurable logic for calculating the utilization fee
(US). The implementation is standalone and does not depend on Telegram or
network requests.

Public functions round results to two decimals and raise :class:`ValueError`
for invalid inputs.

``get_age_bucket``
    Buckets vehicle age into ``"<=3y"`` or ``">3y"``.

``pick_personal_coeff``
    Retrieves a coefficient for personal usage depending on fuel type,
    engine volume and vehicle age.

``calc_util_ed_rub``
    Calculates ``US_ed`` – the base utilization fee without adjustments.

``calc_util_rub``
    Calculates the final utilization fee applying date‑based formulas and
    optional ``not in list`` multiplier (enable by setting
    ``config["not_in_list"] = True`` and providing ``not_list_multiplier``
    in the date rule).
"""

from datetime import date
from typing import Dict, Literal
import copy

from ..models.enums import (
    PersonType,
    UsageType,
    FuelType,
    AgeCategory,
    WrongParamException,
)

VehicleKind = Literal["passenger", "commercial"]


def get_age_bucket(age_years: float) -> AgeCategory:
    """Return age bucket for a vehicle.

    Parameters
    ----------
    age_years:
        Age of the vehicle in years. Must be non‑negative.

    Returns
    -------
    AgeCategory
        ``AgeCategory.UNDER_OR_EQUAL_3`` when ``age_years`` is less than or
        equal to three, otherwise ``AgeCategory.OVER_3``.

    Raises
    ------
    ValueError
        If ``age_years`` is negative.
    """

    if age_years < 0:
        raise WrongParamException("age_years", age_years)
    return AgeCategory.UNDER_OR_EQUAL_3 if age_years <= 3 else AgeCategory.OVER_3


def pick_personal_coeff(
    engine_cc: int,
    fuel: FuelType,
    age_bucket: AgeCategory,
    config: Dict,
) -> float:
    """Pick coefficient for personal usage.

    Parameters
    ----------
    engine_cc:
        Engine displacement in cubic centimeters. For EV and hybrid vehicles
        ``engine_cc`` may be ``0``. For ICE engines it must be positive.
    fuel:
        Fuel type: ``"gasoline"``, ``"diesel"``, ``"hybrid"`` or ``"ev"``.
    age_bucket:
        Age bucket obtained from :func:`get_age_bucket`.
    config:
        Configuration dictionary containing ``"coefficients_personal"``.

    Returns
    -------
    float
        Coefficient for the utilization fee calculation.

    Raises
    ------
    ValueError
        If ``engine_cc`` is invalid, fuel is unknown, or configuration is
        missing.
    """

    if engine_cc < 0:
        raise ValueError("engine_cc must be non-negative")
    if fuel in {FuelType.GASOLINE, FuelType.DIESEL} and engine_cc == 0:
        raise ValueError("engine_cc must be positive for ICE vehicles")

    personal = config.get("coefficients_personal")
    if not personal or age_bucket.value not in personal:
        raise ValueError("Invalid configuration for personal coefficients")

    age_cfg = personal[age_bucket.value]
    if fuel in {FuelType.EV, FuelType.HYBRID}:
        coeff = age_cfg.get(fuel.value)
        if coeff is None:
            raise ValueError("Coefficient for fuel not found in config")
        return float(coeff)

    # ICE engine: determine cylinder capacity bucket
    if engine_cc <= 1000:
        key = "cc<=1000"
    elif engine_cc <= 2000:
        key = "cc1000_2000"
    elif engine_cc <= 3000:
        key = "cc2000_3000"
    elif engine_cc <= 3500:
        key = "cc3000_3500"
    else:
        key = "cc>3500"

    coeff = age_cfg.get(key)
    if coeff is None:
        raise ValueError("Coefficient for engine capacity not found in config")
    return float(coeff)


def calc_util_ed_rub(
    *,
    person_type: PersonType,
    usage: UsageType,
    engine_cc: int,
    fuel: FuelType,
    vehicle_kind: VehicleKind,
    age_years: float,
    config: Dict,
) -> float:
    """Calculate base utilization fee ``US_ed`` in rubles.

    Parameters are validated and the result is rounded to two decimals.
    ``US_ed`` is calculated as ``base_rate(vehicle_kind) * coefficient``.

    Raises
    ------
    ValueError
        On any invalid parameter or missing configuration.
    """

    if not isinstance(person_type, PersonType):
        raise WrongParamException("person_type", person_type)
    if not isinstance(usage, UsageType):
        raise WrongParamException("usage", usage)
    if not isinstance(fuel, FuelType):
        raise WrongParamException("fuel", fuel)
    if vehicle_kind not in {"passenger", "commercial"}:
        raise ValueError("Unknown vehicle kind")

    base_rates = config.get("base_rates_rub")
    if not base_rates or vehicle_kind not in base_rates:
        raise ValueError("Base rate not found in config")
    base_rate = base_rates[vehicle_kind]

    age_bucket = get_age_bucket(age_years)

    if person_type is PersonType.INDIVIDUAL and usage is UsageType.PERSONAL:
        coeff = pick_personal_coeff(engine_cc, fuel, age_bucket, config)
    else:
        # Company or commercial usage
        commercial_cfg = config.get("coefficients_commercial")
        if not commercial_cfg:
            raise ValueError("Commercial coefficients missing in config")
        if fuel in {FuelType.EV, FuelType.HYBRID}:
            key = "ev_or_hybrid"
        else:
            key = "default"
        coeff = commercial_cfg.get(key)
        if coeff is None:
            raise ValueError("Coefficient for commercial use not found")

    us_ed = base_rate * float(coeff)
    return round(us_ed, 2)


def calc_util_rub(
    *,
    person_type: PersonType,
    usage: UsageType,
    engine_cc: int,
    fuel: FuelType,
    vehicle_kind: VehicleKind,
    age_years: float,
    date_decl: date,
    avg_vehicle_cost_rub: float | None,
    actual_costs_rub: float | None,
    config: Dict,
) -> float:
    """Calculate final utilization fee (US) in rubles.

    If a date rule applies and both ``avg_vehicle_cost_rub`` (RS) and
    ``actual_costs_rub`` (SZ) are provided, the formula defined by the rule is
    applied. For rule ``"ed_plus_half_diff"`` the calculation is::

        US = US_ed + (RS - SZ) * half_diff_factor

    To apply a multiplier for vehicles "not in list", set
    ``config["not_in_list"] = True`` and ensure the applicable date rule
    contains ``"not_list_multiplier"``.

    Parameters are validated and the result is rounded to two decimals.
    """

    us_ed = calc_util_ed_rub(
        person_type=person_type,
        usage=usage,
        engine_cc=engine_cc,
        fuel=fuel,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        config=config,
    )

    result = us_ed
    rules_cfg = config.get("date_rules", {})
    applicable_rule = None
    applicable_date = None

    for date_str, rule in rules_cfg.items():
        try:
            rule_date = date.fromisoformat(date_str)
        except ValueError as exc:
            raise ValueError(f"Invalid date in config: {date_str}") from exc
        if date_decl >= rule_date and (applicable_date is None or rule_date > applicable_date):
            applicable_rule = rule
            applicable_date = rule_date

    if (
        applicable_rule
        and applicable_rule.get("formula") == "ed_plus_half_diff"
        and avg_vehicle_cost_rub is not None
        and actual_costs_rub is not None
    ):
        factor = float(applicable_rule.get("half_diff_factor", 0.5))
        result = us_ed + (avg_vehicle_cost_rub - actual_costs_rub) * factor
    else:
        result = us_ed

    if config.get("not_in_list"):
        multiplier = 1.0
        if applicable_rule and "not_list_multiplier" in applicable_rule:
            multiplier = float(applicable_rule["not_list_multiplier"])
        result *= multiplier

    return round(result, 2)


UTIL_CONFIG: Dict = {
    "base_rates_rub": {"passenger": 20000, "commercial": 150000},
    "coefficients_personal": {
        "<=3y": {
            "ev": 0.17,
            "hybrid": 0.17,
            "cc<=1000": 0.17,
            "cc1000_2000": 0.17,
            "cc2000_3000": 0.17,
            "cc3000_3500": 107.67,
            "cc>3500": 137.11,
        },
        ">3y": {
            "ev": 0.26,
            "hybrid": 0.26,
            "cc<=1000": 0.26,
            "cc1000_2000": 0.26,
            "cc2000_3000": 0.26,
            "cc3000_3500": 164.84,
            "cc>3500": 180.24,
        },
    },
    "coefficients_commercial": {"ev_or_hybrid": 33.37, "default": 10.0},
    "date_rules": {
        "2025-05-01": {
            "formula": "ed_plus_half_diff",
            "half_diff_factor": 0.5,
            "not_list_multiplier": 3.0,
        }
    },
}


if __name__ == "__main__":

    # Example 1: individual, personal use
    fee1 = calc_util_rub(
        person_type=PersonType.INDIVIDUAL,
        usage=UsageType.PERSONAL,
        engine_cc=1800,
        fuel=FuelType.GASOLINE,
        vehicle_kind="passenger",
        age_years=2.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(UTIL_CONFIG),
    )
    print(f"Example 1: {fee1} RUB")

    # Example 2: company, commercial EV
    fee2 = calc_util_rub(
        person_type=PersonType.COMPANY,
        usage=UsageType.COMMERCIAL,
        engine_cc=0,
        fuel=FuelType.EV,
        vehicle_kind="commercial",
        age_years=1.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(UTIL_CONFIG),
    )
    print(f"Example 2: {fee2} RUB")

    # Example 3: post-2025 with cost difference and not-in-list multiplier
    config3 = copy.deepcopy(UTIL_CONFIG)
    config3["not_in_list"] = True
    fee3 = calc_util_rub(
        person_type=PersonType.INDIVIDUAL,
        usage=UsageType.PERSONAL,
        engine_cc=2500,
        fuel=FuelType.GASOLINE,
        vehicle_kind="passenger",
        age_years=4.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=800000.0,
        actual_costs_rub=600000.0,
        config=config3,
    )
    print(f"Example 3: {fee3} RUB")
