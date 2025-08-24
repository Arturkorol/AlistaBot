import asyncio
from aiogram import Bot, Dispatcher
from bot_alista.config import TOKEN
from bot_alista.handlers import menu, calculate, cancel, menu_navigation, request, faq

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(cancel.router)
    dp.include_router(menu_navigation.router)
    dp.include_router(request.router)
    dp.include_router(faq.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

