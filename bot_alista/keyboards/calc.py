from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu
from bot_alista.keyboards.common import build_menu


def _build(options: list[str]) -> ReplyKeyboardMarkup:
    return build_menu(options, include_back=True)


def age_keyboard() -> ReplyKeyboardMarkup:
    # Display Russian labels; mapping handled in handlers
    return _build([
        "\u041d\u043e\u0432\u043e\u0435",  # Новое
        "1-3",
        "3-5",
        "5-7",
        "\u0421\u0442\u0430\u0440\u0448\u0435 7",  # Старше 7
    ])


def engine_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\u26fd \u0411\u0435\u043d\u0437\u0438\u043d",      # ⛽ Бензин
        "\ud83d\udee2\ufe0f \u0414\u0438\u0437\u0435\u043b\u044c",  # 🛢️ Дизель
        "\ud83d\udd0c \u042d\u043b\u0435\u043a\u0442\u0440\u043e",  # 🔌 Электро
        "\u267b\ufe0f \u0413\u0438\u0431\u0440\u0438\u0434",  # ♻️ Гибрид
    ])


def owner_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\ud83d\udc64 \u0424\u0438\u0437\u043b\u0438\u0446\u043e",  # 👤 Физлицо
        "\ud83c\udfe2 \u042e\u0440\u043b\u0438\u0446\u043e",        # 🏢 Юрлицо
    ])


def currency_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\ud83d\udcb5 USD",  # 💵 USD
        "\ud83d\udcb6 EUR",  # 💶 EUR
    ])


def power_unit_keyboard() -> ReplyKeyboardMarkup:
    """Select power unit for engine power input."""
    return _build([
        "\u26a1\ufe0f \u043b.\u0441.",  # ⚡ л.с.
        "\u26a1\ufe0f \u043a\u0412\u0442",  # ⚡ кВт
    ])


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    # Russian labels via Unicode escapes to avoid encoding issues
    return _build(["\u0414\u0430", "\u041d\u0435\u0442"])  # Да / Нет


__all__ = [
    "age_keyboard",
    "engine_keyboard",
    "owner_keyboard",
    "currency_keyboard",
    "power_unit_keyboard",
    "yes_no_keyboard",
]
