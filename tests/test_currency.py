from datetime import date
from unittest.mock import MagicMock
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.services import currency


def test_get_rate_passes_day(monkeypatch):
    currency._get_rate.cache_clear()
    conv = MagicMock()
    conv.convert.return_value = 1.23
    monkeypatch.setattr(currency, "_get_converter", lambda: conv)
    day = date(2020, 1, 1)
    rate = currency._get_rate("USD", "EUR", day)
    conv.convert.assert_called_once_with(1, "USD", "EUR", date=day)
    assert rate == 1.23


@pytest.mark.parametrize("code, rate", [("JPY", 0.006), ("CNY", 0.13)])
def test_to_eur_fallback(code, rate, monkeypatch):
    monkeypatch.setattr(
        currency, "_get_rate", MagicMock(side_effect=Exception("fail"))
    )
    assert currency.to_eur(10, code) == pytest.approx(10 * rate)


@pytest.mark.parametrize("code, rate", [("JPY", 0.006), ("CNY", 0.13)])
def test_to_rub_fallback(code, rate, monkeypatch):
    monkeypatch.setattr(
        currency, "_get_rate", MagicMock(side_effect=Exception("fail"))
    )
    expected = 10 * rate * currency._EUR_TO_RUB
    assert currency.to_rub(10, code) == pytest.approx(expected)
