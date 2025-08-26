import pytest
from aiogram import types

import asyncio

from bot_alista.utils.navigation import NavigationManager, NavStep
from bot_alista.utils.reset import reset_to_menu
from bot_alista.states import CalculationStates
from bot_alista.constants import BTN_BACK, BTN_MAIN_MENU


class DummyMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None, **kwargs):
        self.answers.append((text, reply_markup))


class DummyFSM:
    def __init__(self) -> None:
        self.state = None
        self.cleared = False

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.cleared = True


def test_nav_push():
    async def scenario():
        nav = NavigationManager(total_steps=1)
        msg = DummyMessage()
        fsm = DummyFSM()
        kb = types.ReplyKeyboardMarkup(keyboard=[])
        step = NavStep(CalculationStates.person_type, "Prompt", kb)
        await nav.push(msg, fsm, step)
        assert fsm.state == CalculationStates.person_type
        assert msg.answers[0][0] == "Шаг 1/1: Prompt"
        assert msg.answers[0][1] is kb

    asyncio.run(scenario())


def test_handle_nav_back_and_main_menu():
    async def scenario():
        nav = NavigationManager(total_steps=2)
        msg = DummyMessage()
        fsm = DummyFSM()
        kb = types.ReplyKeyboardMarkup(keyboard=[])
        await nav.push(msg, fsm, NavStep(CalculationStates.person_type, "P1", kb))
        await nav.push(msg, fsm, NavStep(CalculationStates.usage_type, "P2", kb))

        back_msg = DummyMessage(BTN_BACK)
        handled = await nav.handle_nav(back_msg, fsm)
        assert handled is True
        assert fsm.state == CalculationStates.person_type
        assert back_msg.answers[0][0].startswith("Шаг 1/2")

        main_msg = DummyMessage(BTN_MAIN_MENU)
        handled = await nav.handle_nav(main_msg, fsm)
        assert handled is True
        assert fsm.cleared is True
        assert nav.stack == []
        assert main_msg.answers[0][0].startswith(BTN_MAIN_MENU)

    asyncio.run(scenario())


def test_reset_to_menu():
    async def scenario():
        msg = DummyMessage()
        fsm = DummyFSM()
        await reset_to_menu(msg, fsm)
        assert fsm.cleared is True
        assert msg.answers[0][0].startswith(BTN_MAIN_MENU)

    asyncio.run(scenario())
