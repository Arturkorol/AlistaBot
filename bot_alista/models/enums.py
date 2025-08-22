from __future__ import annotations

"""Shared enumeration types used across the project."""

from enum import Enum
from typing import Type, TypeVar


class WrongParamException(ValueError):
    """Raised when a parameter cannot be parsed into a required enum."""

    def __init__(self, param: str, value: object) -> None:
        message = f"Invalid value for {param}: {value!r}"
        super().__init__(message)
        self.param = param
        self.value = value


T = TypeVar("T", bound=Enum)


def _cast_enum(enum: Type[T], value: str, param: str) -> T:
    """Cast *value* to *enum* or raise :class:`WrongParamException`."""
    try:
        return enum(value)
    except ValueError as exc:  # pragma: no cover - rewrap for clarity
        raise WrongParamException(param, value) from exc


class PersonType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"

    @classmethod
    def from_str(cls, value: str) -> "PersonType":
        return _cast_enum(cls, value.lower(), "person_type")


class UsageType(str, Enum):
    PERSONAL = "personal"
    COMMERCIAL = "commercial"

    @classmethod
    def from_str(cls, value: str) -> "UsageType":
        return _cast_enum(cls, value.lower(), "usage_type")


class FuelType(str, Enum):
    ICE = "ice"
    HYBRID = "hybrid"
    EV = "ev"

    @classmethod
    def from_str(cls, value: str) -> "FuelType":
        return _cast_enum(cls, value.lower(), "fuel_type")


class AgeCategory(str, Enum):
    """Vehicle age bucket used by utilization fee logic."""

    UNDER_OR_EQUAL_3 = "<=3y"
    OVER_3 = ">3y"

    @classmethod
    def from_str(cls, value: str) -> "AgeCategory":
        return _cast_enum(cls, value, "age_category")

    @classmethod
    def from_age_years(cls, age_years: float) -> "AgeCategory":
        if age_years < 0:
            raise WrongParamException("age_years", age_years)
        return cls.UNDER_OR_EQUAL_3 if age_years <= 3 else cls.OVER_3
