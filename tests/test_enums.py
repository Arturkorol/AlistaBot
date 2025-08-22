import pytest

from bot_alista.models.enums import (
    PersonType,
    UsageType,
    FuelType,
    AgeCategory,
    WrongParamException,
)


def test_enum_parsing_success():
    assert PersonType.from_str("individual") is PersonType.INDIVIDUAL
    assert UsageType.from_str("commercial") is UsageType.COMMERCIAL
    assert FuelType.from_str("ev") is FuelType.EV
    assert FuelType.from_str("gasoline") is FuelType.GASOLINE
    assert FuelType.from_str("diesel") is FuelType.DIESEL
    assert AgeCategory.from_str("<=3y") is AgeCategory.UNDER_OR_EQUAL_3
    assert AgeCategory.from_age_years(4.1) is AgeCategory.OVER_3


def test_enum_parsing_errors():
    with pytest.raises(WrongParamException):
        PersonType.from_str("unknown")
    with pytest.raises(WrongParamException):
        FuelType.from_str("steam")
    with pytest.raises(WrongParamException):
        AgeCategory.from_age_years(-1)
