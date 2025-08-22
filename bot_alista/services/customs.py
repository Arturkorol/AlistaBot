from __future__ import annotations

try:
    from tks_api_official import CustomsCalculator
except Exception:  # pragma: no cover - fallback when package missing
    from .customs_calculator import CustomsCalculator


def calculate_etc(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_etc`."""
    return CustomsCalculator.calculate_etc(*args, **kwargs)


def calculate_ctp(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_ctp`."""
    return CustomsCalculator.calculate_ctp(*args, **kwargs)


def calculate_customs(*args, **kwargs):
    """Proxy to :class:`tks_api_official.CustomsCalculator.calculate_customs`."""
    return CustomsCalculator.calculate_customs(*args, **kwargs)


__all__ = [
    "calculate_etc",
    "calculate_ctp",
    "calculate_customs",
    "CustomsCalculator",
]
