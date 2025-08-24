"""Convenience exports for service layer."""

from .customs_calculator import CustomsCalculator


def calculate_ctp(**kwargs):
    """Return CTP calculation for one-off use."""
    calc = CustomsCalculator()
    calc.set_vehicle_details(**kwargs)
    return calc.calculate_ctp()


def calculate_etc(**kwargs):
    """Return ETC calculation for one-off use."""
    calc = CustomsCalculator()
    calc.set_vehicle_details(**kwargs)
    return calc.calculate_etc()


__all__ = ["calculate_ctp", "calculate_etc", "CustomsCalculator"]

