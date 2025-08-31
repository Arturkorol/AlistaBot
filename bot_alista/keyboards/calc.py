from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu
from bot_alista.keyboards.common import build_menu
from bot_alista.models.constants import SUPPORTED_CURRENCY_CODES


def _build(options: list[str]) -> ReplyKeyboardMarkup:
    return build_menu(options, include_back=True)


def age_keyboard() -> ReplyKeyboardMarkup:
    # Display Russian labels; mapping handled in handlers
    return _build([
        "\u041d\u043e\u0432\u043e\u0435",
        "1-3",
        "3-5",
        "5-7",
        "\u0421\u0442\u0430\u0440\u0448\u0435 7",
    ])


def engine_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\u26fd \u0411\u0435\u043d\u0437\u0438\u043d",
        "\U0001F6E2\ufe0f \u0414\u0438\u0437\u0435\u043b\u044c",
        "\U0001F50C \u042d\u043b\u0435\u043a\u0442\u0440\u043e",
        "\u267b\ufe0f \u0413\u0438\u0431\u0440\u0438\u0434",
    ])


def owner_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\U0001F464 \u0424\u0438\u0437\u043b\u0438\u0446\u043e",
        "\U0001F3E2 \u042e\u0440\u043b\u0438\u0446\u043e",
    ])


def power_unit_keyboard() -> ReplyKeyboardMarkup:
    """Select power unit for engine power input."""
    return _build([
        "\u26a1\ufe0f \u043b.\u0441.",
        "\u26a1\ufe0f \u043a\u0412\u0442",
    ])


def hybrid_type_keyboard() -> ReplyKeyboardMarkup:
    """Select hybrid system subtype."""
    return _build([
        "\u27f3 \u041f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u044b\u0439 \u0433\u0438\u0431\u0440\u0438\u0434",
        "\U0001F50C \u0421\u0435\u0440\u0438\u0439\u043d\u044b\u0439 \u0433\u0438\u0431\u0440\u0438\u0434",
    ])


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    # Russian labels via Unicode escapes to avoid encoding issues
    return _build(["\u0414\u0430", "\u041d\u0435\u0442"])  # Да / Нет


def currency_keyboard() -> ReplyKeyboardMarkup:
    # Dynamically built from supported codes; Russian prompts unchanged elsewhere
    flags = {
        "USD": "\U0001F1FA\U0001F1F8",  # 🇺🇸
        "EUR": "\U0001F1EA\U0001F1FA",  # 🇪🇺
        "JPY": "\U0001F1EF\U0001F1F5",  # 🇯🇵
        "CNY": "\U0001F1E8\U0001F1F3",  # 🇨🇳
    }
    options = [f"{flags.get(code, '')} {code}".strip() for code in SUPPORTED_CURRENCY_CODES]
    return build_menu(options, include_back=False, columns=2)


__all__ = [
    "age_keyboard",
    "engine_keyboard",
    "hybrid_type_keyboard",
    "owner_keyboard",
    "currency_keyboard",
    "power_unit_keyboard",
    "yes_no_keyboard",
]

