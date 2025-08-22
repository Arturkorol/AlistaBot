from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


class CustomsCalculator:
    """Utility loader for customs tariff configuration.

    The class lazily reads :mod:`external/tks_api_official/config.yaml` once and
    caches the resulting dictionary.  This provides a single source of truth for
    all customs related calculations within the bot.
    """

    _tariffs: Dict[str, Any] | None = None

    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """Load tariff configuration from the bundled YAML file."""
        if cls._tariffs is None:
            config_path = (
                Path(__file__).resolve().parents[2]
                / "external"
                / "tks_api_official"
                / "config.yaml"
            )
            with open(config_path, "r", encoding="utf-8") as fh:
                cls._tariffs = json.load(fh)
        return cls._tariffs

    @classmethod
    def get_tariffs(cls) -> Dict[str, Any]:
        """Return cached tariff data."""
        return cls._load_config()
