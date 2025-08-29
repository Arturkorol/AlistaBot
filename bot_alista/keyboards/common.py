from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot_alista.keyboards.navigation import back_menu


def _chunk(items: list[str], n: int) -> list[list[str]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


def build_menu(options: list[str], include_back: bool = True, columns: int = 2) -> ReplyKeyboardMarkup:
    """Build a reply keyboard, chunking options into multiple rows.

    - columns: buttons per row (default 2) to avoid hidden/scroll-only buttons.
    """
    rows: list[list[KeyboardButton]] = []
    for group in _chunk(options, max(1, int(columns))):
        rows.append([KeyboardButton(text=o) for o in group])
    if include_back:
        rows.extend(back_menu().keyboard)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


__all__ = ["build_menu"]
