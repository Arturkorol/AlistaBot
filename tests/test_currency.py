import importlib.util
from pathlib import Path
from datetime import date

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES_PATH = ROOT / "bot_alista" / "services"

spec = importlib.util.spec_from_file_location(
    "services.currency", SERVICES_PATH / "currency.py"
)
currency_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(currency_mod)  # type: ignore[attr-defined]

to_rub = currency_mod.to_rub
to_eur = currency_mod.to_eur


def test_to_rub_uses_fts_rate(monkeypatch):
    monkeypatch.setattr(
        currency_mod,
        "_get_fts_rates",
        lambda d: {"USD": 90.0, "EUR": 100.0},
    )
    assert to_rub(2, "USD", rate_date=date(2024, 1, 1)) == 180.0
    assert to_eur(90, "USD", rate_date=date(2024, 1, 1)) == pytest.approx(81.0)
    assert to_eur(100, "RUB", rate_date=date(2024, 1, 1)) == 1.0
