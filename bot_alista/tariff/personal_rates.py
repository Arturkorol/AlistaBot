from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
from pathlib import Path
from functools import lru_cache
import csv
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class PersonalDutyRate:
    """Per‑cc duty rate (EUR/cc) for individuals (personal use)."""

    min_cc: int
    max_cc: int
    rate_eur_per_cc: float


DEFAULT_RATES_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "personal_rates.csv"
)


@lru_cache(maxsize=1)
def load_personal_rates(path: str | Path | None = None) -> Dict[str, Tuple[PersonalDutyRate, ...]]:
    """Load personal duty rates from ``CSV`` file.

    The file must contain columns ``age_bucket``, ``min_cc``, ``max_cc`` and
    ``rate_eur_per_cc``.  To refresh the rates, replace the CSV with the
    latest official data.
    """

    path = Path(path or DEFAULT_RATES_PATH)
    data: Dict[str, list[PersonalDutyRate]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            bucket = row["age_bucket"]
            data.setdefault(bucket, []).append(
                PersonalDutyRate(
                    int(row["min_cc"]),
                    int(row["max_cc"]),
                    float(row["rate_eur_per_cc"]),
                )
            )
    return {k: tuple(v) for k, v in data.items()}


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


def _find_rate_eur_per_cc(
    engine_cc: int, age_years: float, rates: Dict[str, Tuple[PersonalDutyRate, ...]]
) -> float:
    if engine_cc <= 0:
        raise ValueError("Engine displacement must be > 0 cc.")
    bucket = _age_bucket(age_years)
    for row in rates[bucket]:
        if row.min_cc <= engine_cc <= row.max_cc:
            return row.rate_eur_per_cc
    # Fallback to top range if nothing matched
    return rates[bucket][-1].rate_eur_per_cc


def calc_individual_personal_duty_eur(
    engine_cc: int, age_years: float, *, path: str | Path | None = None
) -> float:
    """Duty in EUR for individuals (personal use)."""

    rates = load_personal_rates(path)
    rate = _find_rate_eur_per_cc(engine_cc, age_years, rates)
    return float(Decimal(str(engine_cc * rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
