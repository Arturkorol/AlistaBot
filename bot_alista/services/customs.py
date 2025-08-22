from __future__ import annotations

from typing import Any, Dict


try:  # pragma: no cover - optional external package
    from tks_api_official import CustomsCalculator as _ExternalCalculator
except Exception:  # pragma: no cover - fallback to bundled implementation
    from .customs_calculator import CustomsCalculator as _ExternalCalculator


def calculate_customs(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None, **kwargs) -> Dict[str, float]:
    """Thin wrapper returning a customs breakdown dictionary."""

    calc = _ExternalCalculator(eur_rate=eur_rate, tariffs=tariffs)
    return calc.calculate_ctp(**kwargs)


def calculate_etc(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None, **kwargs) -> Dict[str, float]:
    """Proxy helper that returns ETC including vehicle price."""

    calc = _ExternalCalculator(eur_rate=eur_rate, tariffs=tariffs)
    return calc.calculate_etc(**kwargs)


def calculate_ctp(*, eur_rate: float | None = None, tariffs: Dict[str, Any] | None = None, **kwargs) -> Dict[str, float]:
    """Proxy helper for customs tax payments."""

    calc = _ExternalCalculator(eur_rate=eur_rate, tariffs=tariffs)
    return calc.calculate_ctp(**kwargs)


CustomsCalculator = _ExternalCalculator


__all__ = ["calculate_customs", "calculate_etc", "calculate_ctp", "CustomsCalculator"]
