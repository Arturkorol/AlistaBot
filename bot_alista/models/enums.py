from __future__ import annotations

from enum import Enum


class EnginePowerUnit(Enum):
    KW = "kilowatt"
    HP = "horsepower"


class OwnerType(Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class EngineTypeLegacy(Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class VehicleAgeLegacy(Enum):
    NEW = "new"
    ONE_TO_THREE = "1-3"
    THREE_TO_FIVE = "3-5"
    FIVE_TO_SEVEN = "5-7"
    OVER_SEVEN = "over_7"


__all__ = [
    "EnginePowerUnit",
    "OwnerType",
    "EngineTypeLegacy",
    "VehicleAgeLegacy",
]

