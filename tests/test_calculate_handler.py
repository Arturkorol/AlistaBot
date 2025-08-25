import sys
from pathlib import Path
import asyncio

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

calculate = pytest.importorskip("bot_alista.handlers.calculate")
_run_calculation = calculate._run_calculation
customs_command = calculate.customs_command

from bot_alista.constants import BTN_BACK, BTN_MAIN_MENU


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
        self.answers.append((text, kwargs))


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
    text, kwargs = msg.answers[0]
    assert text == "ok"
    markup = kwargs.get("reply_markup")
    assert markup is not None
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert BTN_BACK in labels and BTN_MAIN_MENU in labels
    assert state.cleared


def test_customs_command_triggers_start(monkeypatch):
    called = {}

    async def fake_start(message, state):
        called["args"] = (message, state)

    monkeypatch.setattr(calculate, "start_calculation", fake_start)
    state = FakeState({})
    msg = FakeMessage()
    asyncio.run(customs_command(msg, state))
    assert called["args"] == (msg, state)
