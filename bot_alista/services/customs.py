from __future__ import annotations

"""Convenience wrappers around :class:`CustomsCalculator`."""

from typing import Any, Dict

try:  # pragma: no cover - optional external package
    from tks_api_official import CustomsCalculator as _ExternalCalculator
except Exception:  # pragma: no cover - fallback to bundled implementation
    from bot_alista.services.customs_calculator import (
        CustomsCalculator as _ExternalCalculator,
    )

_calc: _ExternalCalculator | None = None


def get_calculator(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None) -> _ExternalCalculator:
    """Return a shared ``CustomsCalculator`` instance."""
    global _calc
    if _calc is None or eur_rate is not None or tariffs is not None:
        _calc = _ExternalCalculator(eur_rate=eur_rate or 1.0, tariffs=tariffs)
    return _calc


def calculate_ctp(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None, **vehicle) -> Dict[str, float]:
    """Set vehicle parameters and return customs payments (CTP)."""
    calc = get_calculator(eur_rate=eur_rate, tariffs=tariffs)
    calc.set_vehicle_details(**vehicle)
    return calc.calculate_ctp()


def calculate_etc(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None, **vehicle) -> Dict[str, float]:
    """Set vehicle parameters and return ETC including vehicle price."""
    calc = get_calculator(eur_rate=eur_rate, tariffs=tariffs)
    calc.set_vehicle_details(**vehicle)
    return calc.calculate_etc()


CustomsCalculator = _ExternalCalculator

__all__ = ["get_calculator", "calculate_ctp", "calculate_etc", "CustomsCalculator"]
