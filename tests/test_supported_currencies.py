import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import calculator


@pytest.mark.parametrize("code", calculator.SUPPORTED_CURRENCIES)
def test_get_rate_supported_currencies(monkeypatch, code):
    called = []

    def fake_cached_rate(for_date, c, retries=3, timeout=5.0):
        called.append(c)
        return 42.0

    monkeypatch.setattr("calculator.get_cached_rate", fake_cached_rate)
    rate = calculator._get_rate(code)
    if code == "RUB":
        assert rate == 1.0
        assert called == []
    else:
        assert rate == 42.0
        assert called == [code]


def test_get_rate_unsupported_currency(monkeypatch):
    def fake_cached_rate(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr("calculator.get_cached_rate", fake_cached_rate)
    with pytest.raises(ValueError):
        calculator._get_rate("GBP")
