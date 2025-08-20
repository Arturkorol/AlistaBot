import os
import sys
from types import SimpleNamespace
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from bot_alista.handlers.calculate import _run_calculation

def test_run_calculation_requests_only_needed_codes(monkeypatch):
    state_data = {
        "car_type": "Бензин",
        "currency_code": "USD",
        "amount": 1000.0,
        "engine": 0,
        "power_hp": 0,
        "year": 2020,
    }

    class DummyState:
        async def get_data(self):
            return state_data

        async def update_data(self, **kwargs):
            state_data.update(kwargs)

        async def set_state(self, state):
            state_data["state"] = state

    captured_codes = []

    async def fake_get_cached_rates(for_date, codes, retries=3, timeout=5.0):
        captured_codes.append(set(codes))
        return {code: 1.0 for code in codes}

    monkeypatch.setattr(
        "bot_alista.handlers.calculate.get_cached_rates", fake_get_cached_rates
    )
    async def fake_reset_to_menu(*args, **kwargs):
        return None
    monkeypatch.setattr(
        "bot_alista.handlers.calculate.reset_to_menu", fake_reset_to_menu
    )
    monkeypatch.setattr(
        "bot_alista.handlers.calculate.calc_breakdown_rules",
        lambda **kwargs: {"breakdown": {"customs_value_rub": 100, "duty_rub": 10, "vat_rub": 0, "excise_rub": 0, "total_rub": 10}, "notes": []},
    )
    monkeypatch.setattr(
        "bot_alista.handlers.calculate.format_result_message", lambda **kwargs: "ok"
    )

    async def dummy_answer(*args, **kwargs):
        pass

    dummy_message = SimpleNamespace(answer=dummy_answer)

    asyncio.run(_run_calculation(DummyState(), dummy_message))

    assert captured_codes == [{"USD", "EUR"}]
