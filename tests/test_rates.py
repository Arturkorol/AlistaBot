from datetime import date
import json
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services import rates


def test_get_cached_rates_partial(monkeypatch, tmp_path):
    called = {}

    async def fake_fetch(for_date, codes, retries=3, timeout=5.0):
        called['codes'] = tuple(codes)
        mapping = {"USD": 1.0, "EUR": 2.0, "JPY": 3.0, "CNY": 4.0}
        return {code: mapping[code] for code in codes}

    monkeypatch.setattr(rates, "_fetch_cbr_rates", fake_fetch)
    monkeypatch.setattr(rates, "_cache_file", lambda d: tmp_path / f"{d.isoformat()}.json")

    day = date(2024, 1, 1)

    async def scenario():
        res = await rates.get_cached_rates(day, codes=["USD"])
        assert called['codes'] == ("USD",)
        assert res == {"USD": 1.0}
        data = json.loads((tmp_path / "2024-01-01.json").read_text())
        assert data["rates"] == {"USD": 1.0}

        called.clear()
        res2 = await rates.get_cached_rates(day, codes=["EUR"])
        assert called['codes'] == ("EUR",)
        data = json.loads((tmp_path / "2024-01-01.json").read_text())
        assert data["rates"] == {"USD": 1.0, "EUR": 2.0}
        assert res2 == {"EUR": 2.0}

        called.clear()
        res3 = await rates.get_cached_rates(day, codes=["USD", "EUR"])
        assert 'codes' not in called
        assert res3 == {"USD": 1.0, "EUR": 2.0}

    asyncio.run(scenario())
