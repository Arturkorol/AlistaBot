import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import menu, calculate, navigation, request


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(navigation.router)
    dp.include_router(request.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
