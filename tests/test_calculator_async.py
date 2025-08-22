import asyncio
from datetime import date
from pathlib import Path
import sys

# Ensure repo root on sys.path for module resolution
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import calculator


def test_calculate_individual_async(monkeypatch):
    async def fake_get_cbr_rate(for_date, code):
        return 1.0

    monkeypatch.setattr(calculator, "get_cbr_rate", fake_get_cbr_rate)
    year = date.today().year - 1
    result = asyncio.run(
        calculator.calculate_individual(
            customs_value=10_000,
            currency="EUR",
            engine_cc=2_000,
            production_year=year,
            fuel="бензин",
        )
    )
    assert result["currency_rate"] == 1.0
    assert result["eur_rate"] == 1.0
    assert result["total_rub"] > 0


def test_calculate_company_async(monkeypatch):
    async def fake_get_cbr_rate(for_date, code):
        return 1.0

    monkeypatch.setattr(calculator, "get_cbr_rate", fake_get_cbr_rate)
    year = date.today().year - 1
    result = asyncio.run(
        calculator.calculate_company(
            customs_value=10_000,
            currency="EUR",
            engine_cc=2_000,
            production_year=year,
            fuel="бензин",
            hp=150,
        )
    )
    assert result["currency_rate"] == 1.0
    assert result["eur_rate"] == 1.0
    assert result["total_rub"] > 0
