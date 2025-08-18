import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tariff_engine import _get_rate


def test_uses_cached_rate_when_network_fails(monkeypatch):
    called = []

    def fake_cached_rate(for_date, code, retries=3, timeout=5.0):
        called.append(code)
        rates = {"USD": 80.0, "EUR": 90.0}
        return rates[code]

    def fail_network(*args, **kwargs):
        raise AssertionError("network should not be called")

    # Patch both the module alias and the service function for safety
    monkeypatch.setattr("tariff_engine.get_cached_rate", fake_cached_rate)
    monkeypatch.setattr("bot_alista.services.rates.get_cached_rate", fake_cached_rate)
    monkeypatch.setattr("bot_alista.services.rates._fetch_cbr_rates", fail_network)

    usd = _get_rate("USD")
    eur = _get_rate("EUR")

    assert called == ["USD", "EUR"]
    assert usd == 80.0
    assert eur == 90.0
