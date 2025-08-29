from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from bot_alista.keyboards.main_menu import main_menu
from bot_alista.constants import BTN_MAIN_MENU, BTN_BACK, BTN_EXIT, WELCOME_TEXT, EXIT_TEXT
from bot_alista.utils.reset import reset_to_menu


router = Router()


@router.message(Command("start"), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu())


@router.message(F.text == BTN_MAIN_MENU)
async def go_main_menu(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)


@router.message(F.text == BTN_BACK, StateFilter(None))
async def go_back(message: types.Message, state: FSMContext):
    await reset_to_menu(message, state)


@router.message(F.text == BTN_EXIT)
async def exit_bot(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(EXIT_TEXT, reply_markup=types.ReplyKeyboardRemove())

