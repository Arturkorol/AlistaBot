import requests
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Default fallback tariffs in case fetching fails
DEFAULT_TARIFFS: Dict[str, Any] = {
    "duty": {
        "under_3": {"per_cc": 2.5, "price_percent": 0.48},
        "3_5": [
            (1000, 1.5), (1500, 1.7), (1800, 2.5),
            (2300, 2.7), (3000, 3.0), (99999, 3.6)
        ],
        "over_5": [
            (1000, 3.0), (1500, 3.2), (1800, 3.5),
            (2300, 4.8), (3000, 5.0), (99999, 5.7)
        ],
    },
    "excise": {"over_3000_hp_rub": 511},
    "utilization": {"age_under_3": 2000, "age_over_3": 3400},
    "processing_fee": 5,
}

# Simple in-memory cache per day
_cached_tariffs: Dict[str, Any] | None = None
_cached_date: datetime | None = None

TARIFF_URL = "https://customs.gov.ru/api/tariffs"  # Placeholder URL


def _parse_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts needed fields from JSON structure."""
    try:
        duty = data["duty"]
        excise = data["excise"]
        utilization = data["utilization"]
        fee = data.get("processing_fee", 5)
        return {
            "duty": duty,
            "excise": excise,
            "utilization": utilization,
            "processing_fee": fee,
        }
    except Exception:
        return DEFAULT_TARIFFS


def _parse_xml(text: str) -> Dict[str, Any]:
    """Parses XML tariff data into the standard structure."""
    try:
        root = ET.fromstring(text)
        duty: Dict[str, Any] = {
            "under_3": {"per_cc": float(root.findtext("duty/under_3/per_cc", 2.5)),
                         "price_percent": float(root.findtext("duty/under_3/price_percent", 0.48))},
            "3_5": [],
            "over_5": [],
        }
        for node in root.findall("duty/3_5/rate"):
            duty["3_5"].append((int(node.get("max_cc")), float(node.text)))
        for node in root.findall("duty/over_5/rate"):
            duty["over_5"].append((int(node.get("max_cc")), float(node.text)))
        excise = {
            "over_3000_hp_rub": float(root.findtext("excise/over_3000_hp_rub", 511))
        }
        utilization = {
            "age_under_3": float(root.findtext("utilization/age_under_3", 2000)),
            "age_over_3": float(root.findtext("utilization/age_over_3", 3400)),
        }
        fee = float(root.findtext("processing_fee", 5))
        return {
            "duty": duty,
            "excise": excise,
            "utilization": utilization,
            "processing_fee": fee,
        }
    except Exception:
        return DEFAULT_TARIFFS


def _validate_tariffs(data: Dict[str, Any]) -> bool:
    """Basic validation to ensure required fields exist."""
    try:
        duty = data["duty"]
        under_3 = duty["under_3"]
        if not all(k in under_3 for k in ("per_cc", "price_percent")):
            return False
        if not isinstance(duty.get("3_5"), list) or not isinstance(duty.get("over_5"), list):
            return False
        if "over_3000_hp_rub" not in data["excise"]:
            return False
        util = data["utilization"]
        if not all(k in util for k in ("age_under_3", "age_over_3")):
            return False
        if "processing_fee" not in data:
            return False
    except Exception:
        return False
    return True


def fetch_tariffs() -> Dict[str, Any]:
    """Fetches tariff rates from the Russian customs service with per-day caching."""
    global _cached_tariffs, _cached_date
    today = datetime.today().date()
    if _cached_tariffs and _cached_date == today:
        return _cached_tariffs

    try:
        resp = requests.get(TARIFF_URL, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            tariffs = _parse_json(resp.json())
        else:
            tariffs = _parse_xml(resp.text)
        if not _validate_tariffs(tariffs):
            raise ValueError("invalid data structure")
    except Exception as e:
        logging.warning("Failed to fetch tariffs: %s", e)
        tariffs = DEFAULT_TARIFFS

    _cached_tariffs = tariffs
    _cached_date = today
    return tariffs

