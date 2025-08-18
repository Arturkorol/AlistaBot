from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from ..utils.reset import reset_to_menu

router = Router()


@router.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext) -> None:
    """Handle /cancel command by returning user to the main menu."""
    await reset_to_menu(message, state)
    await message.answer("❌ Действие отменено")


@router.message(StateFilter(None), F.text.in_({"🏠 Главное меню", "⬅ Назад"}))
async def nav_main_menu(message: types.Message, state: FSMContext) -> None:
    """Return to main menu when user presses navigation buttons."""
    await reset_to_menu(message, state)


@router.message(F.text == "❌ Выход")
async def exit_to_menu(message: types.Message, state: FSMContext) -> None:
    """Handle exit button by resetting state and sending a farewell."""
    await reset_to_menu(message, state)
    await message.answer("До встречи!")
