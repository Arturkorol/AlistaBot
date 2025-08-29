from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu
from bot_alista.keyboards.common import build_menu


def _build(options: list[str]) -> ReplyKeyboardMarkup:
    return build_menu(options, include_back=True)


def age_keyboard() -> ReplyKeyboardMarkup:
    # Display Russian labels; mapping handled in handlers
    return _build([
        "\u041d\u043e\u0432\u043e\u0435",  # РќРѕРІРѕРµ
        "1-3",
        "3-5",
        "5-7",
        "\u0421\u0442\u0430\u0440\u0448\u0435 7",  # РЎС‚Р°СЂС€Рµ 7
    ])


def engine_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\u26fd \u0411\u0435\u043d\u0437\u0438\u043d",      # в›Ѕ Р‘РµРЅР·РёРЅ
        "\U0001F6E2\ufe0f \u0414\u0438\u0437\u0435\u043b\u044c",  # рџ›ўпёЏ Р”РёР·РµР»СЊ
        "\U0001F50C \u042d\u043b\u0435\u043a\u0442\u0440\u043e",  # рџ”Њ Р­Р»РµРєС‚СЂРѕ
        "\u267b\ufe0f \u0413\u0438\u0431\u0440\u0438\u0434",  # в™»пёЏ Р“РёР±СЂРёРґ
    ])


def owner_keyboard() -> ReplyKeyboardMarkup:
    return _build([
        "\U0001F464 \u0424\u0438\u0437\u043b\u0438\u0446\u043e",  # рџ‘¤ Р¤РёР·Р»РёС†Рѕ
        "\U0001F3E2 \u042e\u0440\u043b\u0438\u0446\u043e",        # рџЏў Р®СЂР»РёС†Рѕ
    ])


def currency_keyboard() -> ReplyKeyboardMarkup:
    # No back/menu here to keep all 4 currencies visible without scrolling
    from bot_alista.keyboards.common import build_menu
    return build_menu(
        [
            "\U0001F1FA\U0001F1F8 USD",  # 🇺🇸 USD
            "\U0001F1EA\U0001F1FA EUR",  # 🇪🇺 EUR
            "\U0001F1EF\U0001F1F5 JPY",  # 🇯🇵 JPY
            "\U0001F1E8\U0001F1F3 CNY",  # 🇨🇳 CNY
        ],
        include_back=False,
        columns=2,
    )


def power_unit_keyboard() -> ReplyKeyboardMarkup:
    """Select power unit for engine power input."""
    return _build([
        "\u26a1\ufe0f \u043b.\u0441.",  # вљЎ Р».СЃ.
        "\u26a1\ufe0f \u043a\u0412\u0442",  # вљЎ РєР’С‚
    ])


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    # Russian labels via Unicode escapes to avoid encoding issues
    return _build(["\u0414\u0430", "\u041d\u0435\u0442"])  # Р”Р° / РќРµС‚


__all__ = [
    "age_keyboard",
    "engine_keyboard",
    "owner_keyboard",
    "currency_keyboard",
    "power_unit_keyboard",
    "yes_no_keyboard",
]
