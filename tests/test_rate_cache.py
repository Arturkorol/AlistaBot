import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from calculator import calculate_individual


def test_uses_cached_rate_when_network_fails(monkeypatch):
    called = []

    def fake_cached_rate(for_date, code, retries=3, timeout=5.0):
        called.append(code)
        rates = {"USD": 80.0, "EUR": 90.0}
        return rates[code]

    def fail_network(*args, **kwargs):
        raise AssertionError("network should not be called")

    # Patch both the calculator's alias and the service function for safety
    monkeypatch.setattr("calculator.get_cached_rate", fake_cached_rate)
    monkeypatch.setattr("bot_alista.services.rates.get_cached_rate", fake_cached_rate)
    monkeypatch.setattr("bot_alista.services.rates._fetch_cbr_rates", fail_network)

    res = calculate_individual(
        customs_value=100,
        currency="USD",
        engine_cc=1000,
        production_year=2022,
        fuel="Бензин",
    )

    assert called == ["USD", "EUR"]
    assert res["currency_rate"] == 80.0
    assert res["eur_rate"] == 90.0
