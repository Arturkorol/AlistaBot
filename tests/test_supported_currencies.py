import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from bot_alista.tariff_engine import SUPPORTED_CURRENCIES, _get_rate


@pytest.mark.parametrize("code", SUPPORTED_CURRENCIES)
def test_get_rate_supported_currencies(monkeypatch, code):
    called = []

    def fake_cached_rate(for_date, c, retries=3, timeout=5.0):
        called.append(c)
        return 42.0

    monkeypatch.setattr("bot_alista.tariff_engine.get_cached_rate", fake_cached_rate)
    rate = _get_rate(code)
    if code == "RUB":
        assert rate == 1.0
        assert called == []
    else:
        assert rate == 42.0
        assert called == [code]


def test_get_rate_unsupported_currency(monkeypatch):
    def fake_cached_rate(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr("bot_alista.tariff_engine.get_cached_rate", fake_cached_rate)
    with pytest.raises(ValueError):
        _get_rate("GBP")
