from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Set, List

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


def _available_labels(buckets: AgeBuckets) -> List[str]:
    labels: List[str] = []
    if buckets.has_le3:
        labels.append("≤3")
    if buckets.has_3_5:
        labels.append("3–5")
    if buckets.has_5_7:
        labels.append("5–7")
    if buckets.has_gt7:
        labels.append(">7")
    if buckets.has_gt5:
        labels.append(">5")
    return labels


def candidate_ul_labels(actual_age: float, buckets: AgeBuckets) -> List[str]:
    """Return preferred age labels for UL/commercial usage."""

    if actual_age <= 3.0 and buckets.has_le3:
        best = "≤3"
    elif actual_age <= 5.0 and buckets.has_3_5:
        best = "3–5"
    elif actual_age <= 7.0 and buckets.has_5_7:
        best = "5–7"
    elif buckets.has_gt7:
        best = ">7"
    elif buckets.has_gt5:
        best = ">5"
    elif buckets.has_3_5:
        best = "3–5"
    elif buckets.has_5_7:
        best = "5–7"
    elif buckets.has_le3:
        best = "≤3"
    else:
        best = ">7"

    candidates = [best]
    for label in ["≤3", "3–5", "5–7", ">7", ">5"]:
        if label in _available_labels(buckets) and label not in candidates:
            candidates.append(label)
    return candidates


def candidate_fl_labels(user_over3: bool, actual_age: float, buckets: AgeBuckets) -> List[str]:
    """Return preferred age labels for FL (individual) usage."""

    if not user_over3:
        if buckets.has_le3:
            best = "≤3"
        elif buckets.has_3_5:
            best = "3–5"
        elif buckets.has_5_7:
            best = "5–7"
        elif buckets.has_gt7:
            best = ">7"
        elif buckets.has_gt5:
            best = ">5"
        else:
            best = "≤3"
    else:
        if actual_age <= 5.0 and buckets.has_3_5:
            best = "3–5"
        elif actual_age <= 7.0 and buckets.has_5_7:
            best = "5–7"
        elif buckets.has_gt7:
            best = ">7"
        elif buckets.has_gt5:
            best = ">5"
        elif buckets.has_3_5:
            best = "3–5"
        elif buckets.has_5_7:
            best = "5–7"
        elif buckets.has_le3:
            best = "≤3"
        else:
            best = ">7"

    candidates = [best]
    for label in ["≤3", "3–5", "5–7", ">7", ">5"]:
        if label in _available_labels(buckets) and label not in candidates:
            candidates.append(label)
    return candidates
