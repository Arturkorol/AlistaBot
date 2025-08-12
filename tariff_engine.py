from __future__ import annotations

from datetime import date
from typing import Dict, Any, Optional

UTIL_CONFIG: Dict[str, Any] = {
    "base_rates_rub": {
        "passenger": 20000,
        "commercial": 150000,
    },
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
    "coefficients_commercial": {
        "ev_or_hybrid": 33.37,
        "default": 10.00,
    },
    "date_rules": {
        "2025-05-01": {
            "formula": "ed_plus_half_diff",
            "half_diff_factor": 0.5,
        }
    },
}


def get_age_bucket(years: float) -> str:
    """Return age bucket string.

    Parameters
    ----------
    years: float
        Age of vehicle in years. Non‑negative.

    Returns
    -------
    str
        "<=3y" if ``years`` <= 3, otherwise ">3y".
    """
    if years < 0:
        raise ValueError("age_years must be non-negative")
    return "<=3y" if years <= 3 else ">3y"


def _get_engine_bucket(engine_cc: int) -> str:
    """Internal helper returning engine volume bucket key."""
    if engine_cc <= 0:
        raise ValueError("engine_cc must be > 0")
    if engine_cc <= 1000:
        return "cc<=1000"
    if engine_cc <= 2000:
        return "cc1000_2000"
    if engine_cc <= 3000:
        return "cc2000_3000"
    if engine_cc <= 3500:
        return "cc3000_3500"
    return "cc>3500"


def pick_personal_util_coeff(engine_cc: int, fuel_type: str, age_bucket: str, config: Dict[str, Any]) -> float:
    """Pick utilisation coefficient for personal use.

    Parameters
    ----------
    engine_cc: int
        Engine displacement in cubic centimetres. Must be >0.
    fuel_type: str
        'ev', 'hybrid' or 'ice'.
    age_bucket: str
        '<=3y' or '>3y'.
    config: dict
        Configuration providing ``coefficients_personal`` section.

    Returns
    -------
    float
        Coefficient matching the vehicle parameters.
    """
    if fuel_type not in {"ev", "hybrid", "ice"}:
        raise ValueError("fuel_type must be 'ev', 'hybrid' or 'ice'")
    if age_bucket not in config.get("coefficients_personal", {}):
        raise ValueError("age bucket not found in config")

    coeffs = config["coefficients_personal"][age_bucket]
    key = fuel_type
    if fuel_type == "ice":
        key = _get_engine_bucket(engine_cc)
    if key not in coeffs:
        raise ValueError(f"Coefficient for key '{key}' not found")
    return coeffs[key]


def calc_util_ed_rub(
    person_type: str,
    usage_type: str,
    *,
    engine_cc: int,
    fuel_type: str,
    vehicle_kind: str,
    age_years: float,
    config: Dict[str, Any],
) -> float:
    """Calculate base utilisation fee (USed).

    USed = base_rate(vehicle_kind) * coefficient

    For individuals using cars for personal purposes the coefficient is
    chosen from ``coefficients_personal``; otherwise from
    ``coefficients_commercial``.
    """
    if person_type not in {"individual", "company"}:
        raise ValueError("person_type must be 'individual' or 'company'")
    if usage_type not in {"personal", "commercial"}:
        raise ValueError("usage_type must be 'personal' or 'commercial'")
    if vehicle_kind not in config.get("base_rates_rub", {}):
        raise ValueError("vehicle_kind not found in base rates")
    if fuel_type not in {"ev", "hybrid", "ice"}:
        raise ValueError("fuel_type must be 'ev', 'hybrid' or 'ice'")
    if engine_cc <= 0:
        raise ValueError("engine_cc must be > 0")
    if age_years < 0:
        raise ValueError("age_years must be >= 0")

    base_rate = config["base_rates_rub"][vehicle_kind]
    if person_type == "individual" and usage_type == "personal":
        age_bucket = get_age_bucket(age_years)
        coeff = pick_personal_util_coeff(engine_cc, fuel_type, age_bucket, config)
    else:
        if fuel_type in {"ev", "hybrid"}:
            key = "ev_or_hybrid"
        else:
            key = "default"
        coeff = config.get("coefficients_commercial", {}).get(key)
        if coeff is None:
            raise ValueError(f"Coefficient '{key}' not configured")

    return round(base_rate * coeff, 2)


def calc_util_rub(
    *,
    person_type: str,
    usage_type: str,
    engine_cc: int,
    fuel_type: str,
    vehicle_kind: str,
    age_years: float,
    date_decl: date,
    avg_vehicle_cost_rub: Optional[float],
    actual_costs_rub: Optional[float],
    config: Dict[str, Any] = UTIL_CONFIG,
) -> float:
    """Full utilisation fee calculation.

    Parameters
    ----------
    person_type, usage_type, engine_cc, fuel_type, vehicle_kind, age_years
        Parameters forwarded to :func:`calc_util_ed_rub`.
    date_decl: date
        Declaration date.
    avg_vehicle_cost_rub, actual_costs_rub: float | None
        Average vehicle cost (RS) and actual costs (SZ) for formula after
        2025‑05‑01. If any is ``None`` the additional term is skipped.

    Returns
    -------
    float
        Final utilisation fee in rubles rounded to 2 decimals.

    Notes
    -----
    Until 2025‑05‑01:
        ``US = USed``

    From 2025‑05‑01 (inclusive) when rule is present in config:
        ``US = USed + (RS - SZ) * half_diff_factor``
    """
    util_ed = calc_util_ed_rub(
        person_type,
        usage_type,
        engine_cc=engine_cc,
        fuel_type=fuel_type,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        config=config,
    )

    rule_date = date(2025, 5, 1)
    util = util_ed
    if date_decl >= rule_date and "2025-05-01" in config.get("date_rules", {}):
        rule = config["date_rules"]["2025-05-01"]
        if (
            avg_vehicle_cost_rub is not None
            and actual_costs_rub is not None
            and rule.get("formula") == "ed_plus_half_diff"
        ):
            util = util_ed + (avg_vehicle_cost_rub - actual_costs_rub) * rule.get(
                "half_diff_factor", 0.5
            )
        else:
            util = util_ed
    return round(util, 2)


def calc_import_breakdown(
    *,
    customs_value_rub: float,
    duty_rate: float,
    excise_rate: float,
    person_type: str,
    usage_type: Optional[str],
    engine_cc: int,
    fuel_type: str,
    vehicle_kind: str,
    age_years: float,
    date_decl: date,
    avg_vehicle_cost_rub: Optional[float] = None,
    actual_costs_rub: Optional[float] = None,
    config: Dict[str, Any] = UTIL_CONFIG,
) -> Dict[str, Any]:
    """Calculate full import cost breakdown including utilisation fee.

    Parameters
    ----------
    customs_value_rub: float
        Customs value of the vehicle in RUB.
    duty_rate: float
        Duty rate as a fraction (e.g., 0.15 for 15%).
    excise_rate: float
        Excise rate applied to ``customs_value_rub``.
    person_type: str
        'individual' or 'company'.
    usage_type: str | None
        'personal' or 'commercial'. If ``None`` defaults to
        'personal' for individuals and 'commercial' for companies.
    engine_cc, fuel_type, vehicle_kind, age_years, date_decl,
    avg_vehicle_cost_rub, actual_costs_rub
        Parameters for utilisation fee calculation.
    config: dict
        Utilisation fee configuration.

    Returns
    -------
    dict
        {"breakdown": {...}, "util_config_used": config, "notes": [...]}.
    """
    if customs_value_rub < 0:
        raise ValueError("customs_value_rub must be >= 0")
    if duty_rate < 0 or excise_rate < 0:
        raise ValueError("rates must be non-negative")

    customs_value_rub = round(customs_value_rub, 2)
    duty_rub = round(customs_value_rub * duty_rate, 2)
    excise_rub = round(customs_value_rub * excise_rate, 2)
    vat_rub = round((customs_value_rub + duty_rub + excise_rub) * 0.2, 2)

    resolved_usage = (
        "personal" if person_type == "individual" else "commercial"
        if usage_type is None
        else usage_type
    )

    util_rub = calc_util_rub(
        person_type=person_type,
        usage_type=resolved_usage,
        engine_cc=engine_cc,
        fuel_type=fuel_type,
        vehicle_kind=vehicle_kind,
        age_years=age_years,
        date_decl=date_decl,
        avg_vehicle_cost_rub=avg_vehicle_cost_rub,
        actual_costs_rub=actual_costs_rub,
        config=config,
    )
    total_rub = round(
        customs_value_rub + duty_rub + excise_rub + vat_rub + util_rub, 2
    )

    notes = []
    if date_decl >= date(2025, 5, 1) and (
        avg_vehicle_cost_rub is None or actual_costs_rub is None
    ):
        notes.append(
            "Не заданы avg_vehicle_cost_rub/actual_costs_rub — использован только УСed."
        )
    notes.append(
        "Утилизационный сбор рассчитан по конфигурации UTIL_CONFIG; ставки и формулы обновляются без изменения кода."
    )

    return {
        "breakdown": {
            "customs_value_rub": customs_value_rub,
            "duty_rub": duty_rub,
            "excise_rub": excise_rub,
            "vat_rub": vat_rub,
            "util_rub": util_rub,
            "total_rub": total_rub,
        },
        "util_config_used": config,
        "notes": notes,
    }


if __name__ == "__main__":
    from pprint import pprint

    # Example 1: individual, ICE 2500 cc, 7 years, 2025-03-15
    result1 = calc_import_breakdown(
        customs_value_rub=1_000_000,
        duty_rate=0.15,
        excise_rate=0.0,
        person_type="individual",
        usage_type=None,
        engine_cc=2500,
        fuel_type="ice",
        vehicle_kind="passenger",
        age_years=7,
        date_decl=date(2025, 3, 15),
    )
    print("Example 1:")
    pprint(result1)

    # Example 2: individual, EV 2 years, formula with half difference
    result2 = calc_import_breakdown(
        customs_value_rub=2_000_000,
        duty_rate=0.0,
        excise_rate=0.0,
        person_type="individual",
        usage_type="personal",
        engine_cc=1,  # dummy for EV
        fuel_type="ev",
        vehicle_kind="passenger",
        age_years=2,
        date_decl=date(2025, 6, 10),
        avg_vehicle_cost_rub=3_000_000,
        actual_costs_rub=2_800_000,
    )
    print("\nExample 2:")
    pprint(result2)

    # Example 3: company, commercial usage, ICE 3200 cc, 8 years, missing RS/SZ
    result3 = calc_import_breakdown(
        customs_value_rub=1_500_000,
        duty_rate=0.15,
        excise_rate=0.05,
        person_type="company",
        usage_type="commercial",
        engine_cc=3200,
        fuel_type="ice",
        vehicle_kind="commercial",
        age_years=8,
        date_decl=date(2025, 7, 1),
    )
    print("\nExample 3:")
    pprint(result3)

    # Example 4: erroneous fuel_type
    try:
        calc_import_breakdown(
            customs_value_rub=1_000_000,
            duty_rate=0.15,
            excise_rate=0.0,
            person_type="individual",
            usage_type=None,
            engine_cc=2000,
            fuel_type="diesel",
            vehicle_kind="passenger",
            age_years=5,
            date_decl=date(2025, 5, 20),
        )
    except ValueError as err:
        print("\nExample 4: error ->", err)
