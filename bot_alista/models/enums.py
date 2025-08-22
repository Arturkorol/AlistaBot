from __future__ import annotations

from enum import Enum
from typing import Dict, Type, TypeVar, Union


class WrongParamException(ValueError):
    """Raised when an invalid enum value is supplied."""


E = TypeVar("E", bound=Enum)


def _from_mapping(enum_cls: Type[E], mapping: Dict[str, E], value: Union[str, Enum, bool]) -> E:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, Enum):
        # Different enum provided
        raise WrongParamException(f"Invalid {enum_cls.__name__}: {value}")
    key = str(value).strip().lower()
    try:
        return mapping[key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise WrongParamException(f"Invalid {enum_cls.__name__}: {value}") from exc


class FuelType(str, Enum):
    GASOLINE = "Бензин"
    DIESEL = "Дизель"
    HYBRID = "Гибрид"
    ELECTRO = "Электро"

    @classmethod
    def from_str(cls, value: Union[str, "FuelType"]) -> "FuelType":
        mapping = {
            "бензин": cls.GASOLINE,
            "дизель": cls.DIESEL,
            "гибрид": cls.HYBRID,
            "электро": cls.ELECTRO,
            "электрический": cls.ELECTRO,
        }
        return _from_mapping(cls, mapping, value)


class PersonType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"

    @classmethod
    def from_str(cls, value: Union[str, "PersonType"]) -> "PersonType":
        mapping = {
            "физическое лицо": cls.INDIVIDUAL,
            "физлицо": cls.INDIVIDUAL,
            "individual": cls.INDIVIDUAL,
            "юридическое лицо": cls.COMPANY,
            "юрлицо": cls.COMPANY,
            "company": cls.COMPANY,
        }
        return _from_mapping(cls, mapping, value)


class UsageType(str, Enum):
    PERSONAL = "personal"
    COMMERCIAL = "commercial"

    @classmethod
    def from_str(cls, value: Union[str, "UsageType"]) -> "UsageType":
        mapping = {
            "личное": cls.PERSONAL,
            "personal": cls.PERSONAL,
            "коммерческое": cls.COMMERCIAL,
            "commercial": cls.COMMERCIAL,
        }
        return _from_mapping(cls, mapping, value)


class AgeCategory(str, Enum):
    UNDER_3 = "under_3"
    OVER_3 = "over_3"

    @classmethod
    def from_str(cls, value: Union[str, bool, "AgeCategory"]) -> "AgeCategory":
        if isinstance(value, bool):
            return cls.OVER_3 if value else cls.UNDER_3
        mapping = {
            "under_3": cls.UNDER_3,
            "до 3": cls.UNDER_3,
            "нет": cls.UNDER_3,
            "over_3": cls.OVER_3,
            "старше 3": cls.OVER_3,
            "да": cls.OVER_3,
        }
        return _from_mapping(cls, mapping, value)


__all__ = [
    "FuelType",
    "PersonType",
    "UsageType",
    "AgeCategory",
    "WrongParamException",
]
