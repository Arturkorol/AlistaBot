from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class PersonalDutyRate:
    """
    Per-cc duty rate (EUR/cc) for individuals (personal use), bucketed by age × engine cc.
    EDIT THESE VALUES to match your reference calculator exactly.
    """
    min_cc: int
    max_cc: int
    rate_eur_per_cc: float


# Full per-cc table for individuals (personal use).
# Keys are age buckets; values are ordered tuples of engine-cc intervals.
# IMPORTANT: Tune these to match your reference (vl.broker).
PERSONAL_RATES: Dict[str, Tuple[PersonalDutyRate, ...]] = {
    # 1–3 years
    "1_3y": (
        PersonalDutyRate(0, 1000, 3.5),
        PersonalDutyRate(1001, 1500, 5.5),
        PersonalDutyRate(1501, 1800, 5.5),
        PersonalDutyRate(1801, 2300, 6.2),
        PersonalDutyRate(2301, 3000, 5.5),   # was 8.4 → must be 5.5 €/cc
        PersonalDutyRate(3001, 10000, 7.5),
    ),
    # 3–5 years
    "3_5y": (
        PersonalDutyRate(0, 1000, 1.5),
        PersonalDutyRate(1001, 1500, 1.7),
        PersonalDutyRate(1501, 1800, 2.5),
        PersonalDutyRate(1801, 2300, 3.0),
        PersonalDutyRate(2301, 3000, 3.0),   # was 3.5 → must be 3.0 €/cc
        PersonalDutyRate(3001, 10000, 5.5),
    ),
    # 5–7 years
    "5_7y": (
        PersonalDutyRate(0, 1000, 3.0),
        PersonalDutyRate(1001, 1500, 3.2),
        PersonalDutyRate(1501, 1800, 3.5),
        PersonalDutyRate(1801, 2300, 4.8),
        PersonalDutyRate(2301, 3000, 5.7),
        PersonalDutyRate(3001, 10000, 7.5),
    ),
    # > 7 years
    "7p_y": (
        PersonalDutyRate(0, 1000, 3.0),
        PersonalDutyRate(1001, 1500, 3.2),
        PersonalDutyRate(1501, 1800, 3.5),
        PersonalDutyRate(1801, 2300, 5.0),
        PersonalDutyRate(2301, 3000, 5.7),
        PersonalDutyRate(3001, 10000, 5.7),  # was 7.5; must be 5.7
    ),
}

# Customs clearance fee is calculated via
# ``tariff_engine.calc_clearance_fee_rub``.  No fixed constant is stored
# here to avoid drift from the authoritative fee ladder.


def _age_bucket(age_years: float) -> str:
    """
    Returns one of: '1_3y', '3_5y', '5_7y', '7p_y'.
    0–1y falls into the nearest bucket '1_3y'.
    """
    if age_years < 1:
        return "1_3y"
    if 1 <= age_years < 3:
        return "1_3y"
    if 3 <= age_years < 5:
        return "3_5y"
    if 5 <= age_years < 7:
        return "5_7y"
    return "7p_y"


def _find_rate_eur_per_cc(engine_cc: int, age_years: float) -> float:
    if engine_cc <= 0:
        raise ValueError("Engine displacement must be > 0 cc.")
    bucket = _age_bucket(age_years)
    for row in PERSONAL_RATES[bucket]:
        if row.min_cc <= engine_cc <= row.max_cc:
            return row.rate_eur_per_cc
    # Fallback to top range if nothing matched
    return PERSONAL_RATES[bucket][-1].rate_eur_per_cc


def calc_individual_personal_duty_eur(engine_cc: int, age_years: float) -> float:
    """
    Duty in EUR for individuals (personal use) = engine_cc × per-cc rate (EUR/cc).
    """
    rate = _find_rate_eur_per_cc(engine_cc, age_years)
    return round(engine_cc * rate, 2)
