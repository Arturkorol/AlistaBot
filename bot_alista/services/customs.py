from __future__ import annotations

"""Convenience wrappers around :class:`CustomsCalculator`.

The wrapped class now performs its own currency conversion, so these helpers no
longer accept an explicit EUR exchange rate.  Vehicle ``price`` and ``currency``
should be provided directly to :meth:`set_vehicle_details` via keyword
arguments.
"""

from typing import Any, Dict

try:  # pragma: no cover - optional external package
    from tks_api_official import CustomsCalculator as _ExternalCalculator
except Exception:  # pragma: no cover - fallback to bundled implementation
    from .customs_calculator import CustomsCalculator as _ExternalCalculator

_calc: _ExternalCalculator | None = None


def get_calculator(*, tariffs: Dict[str, Any] | None = None) -> _ExternalCalculator:
    """Return a shared ``CustomsCalculator`` instance."""
    global _calc
    if _calc is None or tariffs is not None:
        _calc = _ExternalCalculator(tariffs=tariffs)
    return _calc


def calculate_ctp(*, tariffs: Dict[str, Any] | None = None, **vehicle) -> Dict[str, float]:
    """Set vehicle parameters and return customs payments (CTP)."""
    calc = get_calculator(tariffs=tariffs)
    calc.set_vehicle_details(**vehicle)
    return calc.calculate_ctp()


def calculate_etc(*, tariffs: Dict[str, Any] | None = None, **vehicle) -> Dict[str, float]:
    """Set vehicle parameters and return ETC including vehicle price."""
    calc = get_calculator(tariffs=tariffs)
    calc.set_vehicle_details(**vehicle)
    return calc.calculate_etc()


CustomsCalculator = _ExternalCalculator

__all__ = ["get_calculator", "calculate_ctp", "calculate_etc", "CustomsCalculator"]
