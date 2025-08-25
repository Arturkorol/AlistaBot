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
from functools import lru_cache
from pathlib import Path
import os
import yaml

PersonType = Literal["individual", "company"]
UsageType = Literal["personal", "commercial"]
FuelType = Literal["ice", "hybrid", "ev"]
VehicleKind = Literal["passenger", "commercial"]


def get_age_bucket(age_years: float) -> Literal["<=3y", ">3y"]:
    """Return age bucket for a vehicle.

    Parameters
    ----------
    age_years:
        Age of the vehicle in years. Must be non‑negative.

    Returns
    -------
    Literal["<=3y", ">3y"]
        ``"<=3y"`` when ``age_years`` is less than or equal to three,
        otherwise ``">3y"``.

    Raises
    ------
    ValueError
        If ``age_years`` is negative.
    """

    if age_years < 0:
        raise ValueError("age_years must be non-negative")
    return "<=3y" if age_years <= 3 else ">3y"


def pick_personal_coeff(
    engine_cc: int,
    fuel: FuelType,
    age_bucket: str,
    config: Dict,
) -> float:
    """Pick coefficient for personal usage.

    Parameters
    ----------
    engine_cc:
        Engine displacement in cubic centimeters. For EV and hybrid vehicles
        ``engine_cc`` may be ``0``. For ICE engines it must be positive.
    fuel:
        Fuel type: ``"ice"``, ``"hybrid"`` or ``"ev"``.
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

    if fuel not in {"ice", "hybrid", "ev"}:
        raise ValueError("Unknown fuel type")
    if engine_cc < 0:
        raise ValueError("engine_cc must be non-negative")
    if fuel == "ice" and engine_cc == 0:
        raise ValueError("engine_cc must be positive for ICE vehicles")

    personal = config.get("coefficients_personal")
    if not personal or age_bucket not in personal:
        raise ValueError("Invalid configuration for personal coefficients")

    age_cfg = personal[age_bucket]
    if fuel in {"ev", "hybrid"}:
        coeff = age_cfg.get(fuel)
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

    if person_type not in {"individual", "company"}:
        raise ValueError("Unknown person_type")
    if usage not in {"personal", "commercial"}:
        raise ValueError("Unknown usage type")
    if fuel not in {"ice", "hybrid", "ev"}:
        raise ValueError("Unknown fuel type")
    if vehicle_kind not in {"passenger", "commercial"}:
        raise ValueError("Unknown vehicle kind")

    base_rates = config.get("base_rates_rub")
    if not base_rates or vehicle_kind not in base_rates:
        raise ValueError("Base rate not found in config")
    base_rate = base_rates[vehicle_kind]

    age_bucket = get_age_bucket(age_years)

    if person_type == "individual" and usage == "personal":
        coeff = pick_personal_coeff(engine_cc, fuel, age_bucket, config)
    else:
        # Company or commercial usage
        commercial_cfg = config.get("coefficients_commercial")
        if not commercial_cfg:
            raise ValueError("Commercial coefficients missing in config")
        if fuel in {"ev", "hybrid"}:
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
    config: Dict | None = None,
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

    config = config or load_util_config()

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

    if applicable_rule and applicable_rule.get("formula") == "ed_plus_half_diff":
        if avg_vehicle_cost_rub is None or actual_costs_rub is None:
            raise ValueError("avg_vehicle_cost_rub and actual_costs_rub are required")
        if avg_vehicle_cost_rub < 0 or actual_costs_rub < 0:
            raise ValueError("Cost values must be non-negative")
        diff = max(avg_vehicle_cost_rub - actual_costs_rub, 0)
        factor = float(applicable_rule.get("half_diff_factor", 0.5))
        result = us_ed + diff * factor
    else:
        result = us_ed

    if config.get("not_in_list"):
        multiplier = 1.0
        if applicable_rule and "not_list_multiplier" in applicable_rule:
            multiplier = float(applicable_rule["not_list_multiplier"])
        result *= multiplier

    return round(result, 2)


DEFAULT_UTIL_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "util_fee.yaml"
)

@lru_cache(maxsize=1)
def load_util_config(path: str | Path | None = None) -> Dict:
    """Load utilization fee configuration from YAML.

    The path can be overridden by ``UTIL_FEE_CONFIG`` environment variable.
    The result is cached to avoid repeated disk access. Call
    ``load_util_config.cache_clear()`` to force reload when needed.
    """

    env_path = os.environ.get("UTIL_FEE_CONFIG")
    path = Path(env_path or path or DEFAULT_UTIL_CONFIG_PATH)
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


if __name__ == "__main__":

    # Example 1: individual, personal use
    fee1 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=1800,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=2.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(load_util_config()),
    )
    print(f"Example 1: {fee1} RUB")

    # Example 2: company, commercial EV
    fee2 = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=0,
        fuel="ev",
        vehicle_kind="commercial",
        age_years=1.0,
        date_decl=date(2024, 6, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=copy.deepcopy(load_util_config()),
    )
    print(f"Example 2: {fee2} RUB")

    # Example 3: post-2025 with cost difference and not-in-list multiplier
    config3 = copy.deepcopy(load_util_config())
    config3["not_in_list"] = True
    fee3 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=2500,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=4.0,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=800000.0,
        actual_costs_rub=600000.0,
        config=config3,
    )
    print(f"Example 3: {fee3} RUB")
