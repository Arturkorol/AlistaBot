"""Utility functions for calculating utilization fee (US).

This module implements a simplified configurable algorithm used for
calculating utilization fee rates in the United States.  The logic is
fully standalone and does not require network access or Telegram
integration.

The behaviour of the functions is driven by a configuration dictionary.
See ``UTIL_CONFIG`` at the end of the file for the default values.

``not_in_list`` multiplier
--------------------------
To apply the ``not_list_multiplier`` defined in ``date_rules`` pass a
configuration with ``{"not_in_list": True}`` when calling
:func:`calc_util_rub`.  If the flag is absent or ``False`` the
multiplier is ignored.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Literal

PersonType = Literal["individual", "company"]
UsageType = Literal["personal", "commercial"]
FuelType = Literal["ice", "hybrid", "ev"]
VehicleKind = Literal["passenger", "commercial"]


AGE_BUCKETS = ("<=3y", ">3y")


def get_age_bucket(age_years: float) -> Literal["<=3y", ">3y"]:
    """Return the age bucket identifier for a vehicle.

    Parameters
    ----------
    age_years:
        Age of the vehicle in years.  Must be non‑negative.

    Returns
    -------
    Literal["<=3y", ">3y"]
        ``"<=3y"`` if ``age_years`` is less than or equal to three,
        otherwise ``">3y"``.

    Raises
    ------
    ValueError
        If ``age_years`` is negative.
    """

    if age_years < 0:
        raise ValueError("age_years must be non-negative")
    return "<=3y" if age_years <= 3 else ">3y"


def _engine_bucket(engine_cc: int) -> str:
    """Internal helper returning the engine volume bucket key."""

    if engine_cc <= 0:
        raise ValueError("engine_cc must be positive")
    if engine_cc <= 1000:
        return "cc<=1000"
    if engine_cc <= 2000:
        return "cc1000_2000"
    if engine_cc <= 3000:
        return "cc2000_3000"
    if engine_cc <= 3500:
        return "cc3000_3500"
    return "cc>3500"


def pick_personal_coeff(
    engine_cc: int,
    fuel: FuelType,
    age_bucket: str,
    config: Dict,
) -> float:
    """Pick a coefficient for personal use vehicles.

    Parameters
    ----------
    engine_cc:
        Engine displacement in cubic centimetres.
    fuel:
        Type of fuel used by the vehicle.
    age_bucket:
        Age bucket identifier obtained from :func:`get_age_bucket`.
    config:
        Configuration dictionary containing ``"coefficients_personal"``.

    Returns
    -------
    float
        Coefficient value corresponding to the provided inputs.

    Raises
    ------
    ValueError
        If required configuration entries are missing or inputs are
        inconsistent.
    """

    personal_cfg = config.get("coefficients_personal")
    if not personal_cfg or age_bucket not in personal_cfg:
        raise ValueError("personal coefficients configuration missing")

    age_cfg = personal_cfg[age_bucket]

    if fuel in {"ev", "hybrid"}:
        key = fuel
    else:
        key = _engine_bucket(engine_cc)

    if key not in age_cfg:
        raise ValueError(f"coefficient for key '{key}' not found")
    return float(age_cfg[key])


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
    """Calculate the utilization fee calculation element (``US_ed``).

    ``US_ed = base_rate(vehicle_kind) * coefficient`` where the
    coefficient depends on ``person_type``, ``usage`` and other
    parameters.

    Parameters
    ----------
    person_type, usage, engine_cc, fuel, vehicle_kind, age_years, config
        See function :func:`calc_util_rub` for full parameter meaning.

    Returns
    -------
    float
        The value of ``US_ed`` in roubles, rounded to two decimals.

    Raises
    ------
    ValueError
        If inputs are inconsistent or required configuration entries are
        missing.
    """

    base_rates = config.get("base_rates_rub")
    if not base_rates or vehicle_kind not in base_rates:
        raise ValueError("base rate configuration missing")
    base_rate = float(base_rates[vehicle_kind])

    age_bucket = get_age_bucket(age_years)

    if person_type == "individual" and usage == "personal":
        coeff = pick_personal_coeff(engine_cc, fuel, age_bucket, config)
    elif person_type == "company" and usage == "commercial":
        commercial_cfg = config.get("coefficients_commercial") or {}
        key = "ev_or_hybrid" if fuel in {"ev", "hybrid"} else "default"
        if key not in commercial_cfg:
            raise ValueError("commercial coefficients configuration missing")
        coeff = float(commercial_cfg[key])
    else:
        raise ValueError("unsupported combination of person_type and usage")

    return round(base_rate * coeff, 2)


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
    """Calculate the utilization fee (``US``) in roubles.

    Parameters
    ----------
    person_type, usage, engine_cc, fuel, vehicle_kind, age_years
        See :func:`calc_util_ed_rub` for details.
    date_decl:
        Date of the customs declaration.
    avg_vehicle_cost_rub:
        Average cost of the vehicle (``RS``). Must be provided together
        with ``actual_costs_rub`` when the formula requires a
        cost difference.
    actual_costs_rub:
        Actual costs (``SZ``). Must be provided together with
        ``avg_vehicle_cost_rub`` when the formula requires a cost
        difference.
    config:
        Configuration dictionary.  To enable the
        ``not_list_multiplier`` set ``{"not_in_list": True}`` in this
        dictionary.

    Returns
    -------
    float
        The utilization fee in roubles rounded to two decimals.

    Raises
    ------
    ValueError
        If cost inputs are incomplete or required configuration entries
        are missing.
    """

    if (avg_vehicle_cost_rub is None) != (actual_costs_rub is None):
        raise ValueError("both avg_vehicle_cost_rub and actual_costs_rub must be provided together")

    us_ed = calc_util_ed_rub(
        person_type=person_type,
        usage=usage,
        engine_cc=engine_cc,
        fuel=fuel,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        config=config,
    )

    rules = config.get("date_rules", {})
    applicable_rule: Dict | None = None
    applicable_date: date | None = None
    for rule_date_str, rule_cfg in rules.items():
        rule_date = date.fromisoformat(rule_date_str)
        if date_decl >= rule_date and (applicable_date is None or rule_date > applicable_date):
            applicable_date = rule_date
            applicable_rule = rule_cfg

    us = us_ed
    if applicable_rule:
        formula = applicable_rule.get("formula")
        if (
            formula == "ed_plus_half_diff"
            and avg_vehicle_cost_rub is not None
            and actual_costs_rub is not None
        ):
            factor = float(applicable_rule.get("half_diff_factor", 0.5))
            us = us_ed + (avg_vehicle_cost_rub - actual_costs_rub) * factor

        if config.get("not_in_list") and "not_list_multiplier" in applicable_rule:
            us *= float(applicable_rule["not_list_multiplier"])

    return round(us, 2)


UTIL_CONFIG = {
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
    # Example 1: individual/personal ICE car before 2025
    fee1 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=1600,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=2,
        date_decl=date(2024, 12, 1),
        avg_vehicle_cost_rub=None,
        actual_costs_rub=None,
        config=UTIL_CONFIG,
    )
    print("Example 1 fee:", fee1)

    # Example 2: company/commercial EV with cost difference after 2025
    fee2 = calc_util_rub(
        person_type="company",
        usage="commercial",
        engine_cc=0,
        fuel="ev",
        vehicle_kind="commercial",
        age_years=1,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=1_000_000,
        actual_costs_rub=800_000,
        config=UTIL_CONFIG,
    )
    print("Example 2 fee:", fee2)

    # Example 3: not in list multiplier
    custom_cfg = dict(UTIL_CONFIG)
    custom_cfg["not_in_list"] = True
    fee3 = calc_util_rub(
        person_type="individual",
        usage="personal",
        engine_cc=4000,
        fuel="ice",
        vehicle_kind="passenger",
        age_years=5,
        date_decl=date(2025, 6, 1),
        avg_vehicle_cost_rub=900_000,
        actual_costs_rub=700_000,
        config=custom_cfg,
    )
    print("Example 3 fee (not in list):", fee3)
