"""Convenience exports for service layer."""

from .customs_calculator import CustomsCalculator

CONFIG_PATH = "external/tks_api_official/config.yaml"


def calculate_ctp(**kwargs):
    """Return CTP calculation for one-off use."""
    calc = CustomsCalculator(CONFIG_PATH)
    calc.set_vehicle_details(**kwargs)
    return calc.calculate_ctp()


def calculate_etc(**kwargs):
    """Return ETC calculation for one-off use."""
    calc = CustomsCalculator(CONFIG_PATH)
    calc.set_vehicle_details(**kwargs)
    return calc.calculate_etc()


def calculate_auto(**kwargs):
    """Return automatic ETC/CTP calculation for one-off use."""
    calc = CustomsCalculator(CONFIG_PATH)
    calc.set_vehicle_details(**kwargs)
    return calc.calculate_auto()


__all__ = [
    "calculate_ctp",
    "calculate_etc",
    "calculate_auto",
    "CustomsCalculator",
]

