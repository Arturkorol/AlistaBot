import requests
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from typing import Any

from .customs_calculator import CustomsCalculator

# Simple in-memory cache per day
_cached_tariffs: dict[str, Any] | None = None
_cached_date: datetime | None = None

TARIFF_URL = "https://customs.gov.ru/api/tariffs"  # Placeholder URL


def _parse_json(data: dict[str, Any]) -> dict[str, Any]:
    """Extracts needed fields from JSON structure."""
    fallback = CustomsCalculator.get_tariffs()
    try:
        duty = data["duty"]
        excise = data["excise"]
        utilization = data["utilization"]
        fee = data["processing_fee"]
        return {
            "duty": duty,
            "excise": excise,
            "utilization": utilization,
            "processing_fee": fee,
        }
    except Exception:
        return fallback


def _parse_xml(text: str) -> dict[str, Any]:
    """Parses XML tariff data into the standard structure."""
    fallback = CustomsCalculator.get_tariffs()
    try:
        root = ET.fromstring(text)
        duty: dict[str, Any] = {
            "under_3": {
                "per_cc": float(
                    root.findtext(
                        "duty/under_3/per_cc",
                        fallback["duty"]["under_3"]["per_cc"],
                    )
                ),
                "price_percent": float(
                    root.findtext(
                        "duty/under_3/price_percent",
                        fallback["duty"]["under_3"]["price_percent"],
                    )
                ),
            },
            "3_5": [],
            "over_5": [],
        }
        for node in root.findall("duty/3_5/rate"):
            duty["3_5"].append((int(node.get("max_cc")), float(node.text)))
        for node in root.findall("duty/over_5/rate"):
            duty["over_5"].append((int(node.get("max_cc")), float(node.text)))
        excise = {
            "over_3000_hp_rub": float(
                root.findtext(
                    "excise/over_3000_hp_rub",
                    fallback["excise"]["over_3000_hp_rub"],
                )
            )
        }
        utilization = {
            "age_under_3": float(
                root.findtext(
                    "utilization/age_under_3",
                    fallback["utilization"]["age_under_3"],
                )
            ),
            "age_over_3": float(
                root.findtext(
                    "utilization/age_over_3",
                    fallback["utilization"]["age_over_3"],
                )
            ),
        }
        fee = float(root.findtext("processing_fee", fallback["processing_fee"]))
        return {
            "duty": duty,
            "excise": excise,
            "utilization": utilization,
            "processing_fee": fee,
        }
    except Exception:
        return fallback


def _validate_tariffs(data: dict[str, Any]) -> bool:
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


def fetch_tariffs() -> dict[str, Any]:
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
        tariffs = CustomsCalculator.get_tariffs()

    _cached_tariffs = tariffs
    _cached_date = today
    return tariffs

