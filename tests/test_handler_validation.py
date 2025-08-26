import sys
from pathlib import Path
import asyncio
from datetime import date

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

calculate = pytest.importorskip("bot_alista.handlers.calculate")
from bot_alista.constants import (
    ENGINE_CC_MIN,
    ENGINE_CC_MAX,
    HP_MIN,
    HP_MAX,
    AGE_MAX,
    ERROR_ENGINE,
    ERROR_POWER,
    ERROR_YEAR,
)


class FakeState:
    def __init__(self, data):
        self.data = data

    async def get_data(self):
        return self.data

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)


class FakeNav:
    def __init__(self):
        self.pushed = []

    async def handle_nav(self, message, state):
        return False

    async def push(self, message, state, step):
        self.pushed.append(step)


def test_get_engine_range_validation():
    state = FakeState({"_nav": FakeNav()})
    msg = FakeMessage(str(ENGINE_CC_MIN - 1))
    asyncio.run(calculate.get_engine(msg, state))
    assert msg.answers[0] == ERROR_ENGINE

    msg = FakeMessage(str(ENGINE_CC_MAX + 1))
    asyncio.run(calculate.get_engine(msg, state))
    assert msg.answers[-1] == ERROR_ENGINE

    msg = FakeMessage(str(ENGINE_CC_MIN))
    state = FakeState({"_nav": FakeNav()})
    asyncio.run(calculate.get_engine(msg, state))
    assert state.data["engine"] == ENGINE_CC_MIN


def test_get_power_range_validation():
    state = FakeState({"_nav": FakeNav()})
    msg = FakeMessage(str(HP_MIN - 1))
    asyncio.run(calculate.get_power(msg, state))
    assert msg.answers[0] == ERROR_POWER

    msg = FakeMessage(str(HP_MAX + 1))
    asyncio.run(calculate.get_power(msg, state))
    assert msg.answers[-1] == ERROR_POWER

    msg = FakeMessage(str(HP_MIN))
    state = FakeState({"_nav": FakeNav()})
    asyncio.run(calculate.get_power(msg, state))
    assert round(state.data["power_hp"], 1) == float(HP_MIN)


def test_get_year_validation():
    min_year = date.today().year - AGE_MAX
    current_year = date.today().year

    state = FakeState({"_nav": FakeNav()})
    msg = FakeMessage(str(min_year))
    asyncio.run(calculate.get_year(msg, state))
    assert state.data["year"] == min_year

    state = FakeState({})
    msg = FakeMessage(str(current_year + 1))
    asyncio.run(calculate.get_year(msg, state))
    expected = f"{ERROR_YEAR} ({min_year}-{current_year})."
    assert msg.answers[0] == expected

    msg = FakeMessage("abcd")
    asyncio.run(calculate.get_year(msg, state))
    assert msg.answers[-1] == expected
