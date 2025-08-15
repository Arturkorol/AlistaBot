from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Set

@dataclass(frozen=True)
class AgeBuckets:
    has_le3: bool
    has_3_5: bool
    has_5_7: bool
    has_gt7: bool
    has_gt5: bool

def _labels_set(labels: Iterable[str]) -> Set[str]:
    return { (s or "").strip() for s in labels if (s or "").strip() }

def detect_buckets(available_labels: Iterable[str]) -> AgeBuckets:
    L = _labels_set(available_labels)
    return AgeBuckets(
        has_le3=("≤3" in L or "<=3" in L or "1–3" in L or "1-3" in L or "до 3" in L),
        has_3_5=("3–5" in L or "3-5" in L),
        has_5_7=("5–7" in L or "5-7" in L),
        has_gt7=(">7" in L or "7+" in L or "старше 7" in L or "более 7" in L),
        has_gt5=(">5" in L or "5+" in L or "старше 5" in L or "более 5" in L),
    )

def compute_actual_age_years(production_year: int, decl_date: date) -> float:
    # conservative: assume Dec 31st if month/day unknown
    prod = date(production_year, 12, 31)
    delta = decl_date - prod
    return max(0.0, delta.days / 365.2425)

def pick_ul_age_label(actual_age: float, buckets: AgeBuckets) -> str:
    """
    For UL we always use factual age.
    Priority: ≤3 → 3–5 → 5–7 → >7 (or >5).
    """
    if actual_age <= 3.0 and buckets.has_le3:
        return "≤3"
    if actual_age <= 5.0 and buckets.has_3_5:
        return "3–5"
    if actual_age <= 7.0 and buckets.has_5_7:
        return "5–7"
    if buckets.has_gt7:
        return ">7"
    if buckets.has_gt5:
        return ">5"
    # last resort: choose the youngest available in order
    if buckets.has_3_5: return "3–5"
    if buckets.has_5_7: return "5–7"
    if buckets.has_le3: return "≤3"
    return ">7"

def pick_fl_age_label(user_over3: bool, actual_age: float, buckets: AgeBuckets) -> str:
    """
    For FL:
      - If user chose "not older than 3": force ≤3 (or nearest younger).
      - If user chose "older than 3": choose among 3–5 / 5–7 / >7 (or >5) by actual age.
    """
    if not user_over3:
        # Prefer ≤3; if absent, pick the youngest available
        if buckets.has_le3: return "≤3"
        if buckets.has_3_5: return "3–5"
        if buckets.has_5_7: return "5–7"
        if buckets.has_gt7: return ">7"
        if buckets.has_gt5: return ">5"
        return "≤3"

    # user_over3 = True
    if actual_age <= 5.0 and buckets.has_3_5:
        return "3–5"
    if actual_age <= 7.0 and buckets.has_5_7:
        return "5–7"
    if buckets.has_gt7:
        return ">7"
    if buckets.has_gt5:
        return ">5"
    # fallback if 3–5/5–7 missing:
    if buckets.has_3_5: return "3–5"
    if buckets.has_5_7: return "5–7"
    # worst-case: can't distinguish; push to >7 or ≤3 if only that exists
    if buckets.has_le3: return "≤3"
    return ">7"


def candidate_fl_labels(user_over3: bool, actual_age: float, buckets: AgeBuckets) -> list[str]:
    """Ordered list of possible age labels for FL with graceful fallback."""
    order: list[str] = []
    if not user_over3:
        if buckets.has_le3: order.append("≤3")
        if buckets.has_3_5: order.append("3–5")
        if buckets.has_5_7: order.append("5–7")
        if buckets.has_gt7: order.append(">7")
        if buckets.has_gt5: order.append(">5")
        if not order:
            order.append("≤3")
        return order

    # user_over3 True
    if actual_age <= 5.0 and buckets.has_3_5:
        order.append("3–5")
    if actual_age <= 7.0 and buckets.has_5_7:
        order.append("5–7")
    if buckets.has_gt7:
        order.append(">7")
    if buckets.has_gt5:
        order.append(">5")
    if buckets.has_3_5 and "3–5" not in order:
        order.append("3–5")
    if buckets.has_5_7 and "5–7" not in order:
        order.append("5–7")
    if buckets.has_le3:
        order.append("≤3")
    if not order:
        order.append(">7")
    return order


def candidate_ul_labels(actual_age: float, buckets: AgeBuckets) -> list[str]:
    """Ordered list of possible age labels for UL with graceful fallback."""
    order: list[str] = []
    if actual_age <= 3.0 and buckets.has_le3:
        order.append("≤3")
    if actual_age <= 5.0 and buckets.has_3_5 and "3–5" not in order:
        order.append("3–5")
    if actual_age <= 7.0 and buckets.has_5_7 and "5–7" not in order:
        order.append("5–7")
    if buckets.has_gt7:
        order.append(">7")
    if buckets.has_gt5 and ">5" not in order:
        order.append(">5")
    if buckets.has_3_5 and "3–5" not in order:
        order.append("3–5")
    if buckets.has_5_7 and "5–7" not in order:
        order.append("5–7")
    if buckets.has_le3 and "≤3" not in order:
        order.append("≤3")
    if not order:
        order.append(">7")
    return order
