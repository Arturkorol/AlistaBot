import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import menu, calculate, request, cancel, menu_navigation
from services.customs_rates import schedule_daily_rate_fetch

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(request.router)
    dp.include_router(cancel.router)
    dp.include_router(menu_navigation.router)

    asyncio.create_task(schedule_daily_rate_fetch())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
