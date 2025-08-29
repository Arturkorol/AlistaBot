import sys
from pathlib import Path
import asyncio

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.handlers.calculate import _run_calculation


class FakeState:
    def __init__(self, data):
        self.data = data
        self.cleared = False

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, *args, **kwargs):
        pass

    async def clear(self):
        self.cleared = True


class FakeMessage:
    def __init__(self):
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)


def test_run_calculation(monkeypatch):
    async def fake_rates(date, codes):
        return {"EUR": 1.0}

    monkeypatch.setattr("bot_alista.handlers.calculate.get_cached_rates", fake_rates)

    def fake_format(**kwargs):
        return "ok"

    monkeypatch.setattr("bot_alista.handlers.calculate.format_result_message", fake_format)

    state = FakeState(
        {
            "car_type": "gasoline",
            "currency_code": "EUR",
            "amount": 10000.0,
            "engine": 2000,
            "power_hp": 150,
            "year": 2018,
            "age_over_3": True,
        }
    )
    msg = FakeMessage()
    asyncio.run(_run_calculation(state, msg))
    assert "ok" in msg.answers[0]
    assert state.cleared