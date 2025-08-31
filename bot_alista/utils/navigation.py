from __future__ import annotations

import re
from dataclasses import dataclass
from functools import wraps
from typing import List

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State

from bot_alista.constants import BTN_BACK, BTN_MAIN_MENU
from bot_alista.utils.reset import reset_to_menu


@dataclass
class NavStep:
    state: State
    prompt: str
    kb: types.ReplyKeyboardMarkup


class NavigationManager:
    """Simple navigation stack with back/main menu handling."""

    def __init__(self, total_steps: int) -> None:
        self.total_steps = total_steps
        self.stack: List[NavStep] = []

    def _strip_step_prefix(self, text: str) -> str:
        """Remove leading "Шаг X/Y:" or "Step X/Y:" from prompts to avoid duplication."""
        try:
            # Match either Russian "Шаг" or English "Step"
            return re.sub(r"^\s*(?:\u0428\u0430\u0433|Step)\s+\d+/\d+:\s*", "", text).strip()
        except Exception:
            return text

    async def push(
        self,
        message: types.Message,
        fsm: FSMContext,
        step: NavStep,
    ) -> None:
        self.stack.append(step)
        await fsm.set_state(step.state)
        cur = min(len(self.stack), self.total_steps)
        prompt = self._strip_step_prefix(step.prompt)
        await message.answer(
            f"\u0428\u0430\u0433 {cur}/{self.total_steps}: {prompt}",
            reply_markup=step.kb,
        )

    async def handle_nav(self, message: types.Message, fsm: FSMContext) -> bool:
        if message.text == BTN_MAIN_MENU:
            await reset_to_menu(message, fsm)
            self.stack.clear()
            return True
        if message.text == BTN_BACK and len(self.stack) > 1:
            self.stack.pop()
            prev = self.stack[-1]
            await fsm.set_state(prev.state)
            cur = min(len(self.stack), self.total_steps)
            prompt = self._strip_step_prefix(prev.prompt)
            await message.answer(
                f"\u0428\u0430\u0433 {cur}/{self.total_steps}: {prompt}",
                reply_markup=prev.kb,
            )
            return True
        return False


def with_nav(handler):
    @wraps(handler)
    async def wrapped(message: types.Message, state: FSMContext, *args, **kwargs):
        data = await state.get_data()
        nav: NavigationManager | None = data.get("_nav")
        if nav and await nav.handle_nav(message, state):
            return
        return await handler(message, state, nav=nav, *args, **kwargs)

    return wrapped

