import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_alista.models import FuelType, PersonType, UsageType, AgeCategory, WrongParamException


def test_enum_parsing():
    assert FuelType.from_str("Бензин") is FuelType.GASOLINE
    assert PersonType.from_str("физическое лицо") is PersonType.INDIVIDUAL
    assert UsageType.from_str("Коммерческое") is UsageType.COMMERCIAL
    assert AgeCategory.from_str("да") is AgeCategory.OVER_3


def test_enum_invalid_value():
    with pytest.raises(WrongParamException):
        FuelType.from_str("water")
    with pytest.raises(WrongParamException):
        PersonType.from_str("alien")
