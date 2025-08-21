"""Wrappers around the official TKS customs calculator."""
from __future__ import annotations

from tks_api_official import CustomsCalculator

_calculator = CustomsCalculator()


def calculate_etc(*args, **kwargs):
    """Proxy to :meth:`CustomsCalculator.calculate_etc`."""
    return _calculator.calculate_etc(*args, **kwargs)


def calculate_ctp(*args, **kwargs):
    """Proxy to :meth:`CustomsCalculator.calculate_ctp`."""
    return _calculator.calculate_ctp(*args, **kwargs)


__all__ = ["calculate_etc", "calculate_ctp", "CustomsCalculator"]
