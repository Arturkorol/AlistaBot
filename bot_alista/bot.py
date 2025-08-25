import asyncio
from aiogram import Bot, Dispatcher
from bot_alista.settings import settings
from bot_alista.handlers import menu, calculate, cancel, menu_navigation, request, faq
from bot_alista.services.rates import init_rates_session, close_rates_session


async def on_startup(_):
    await init_rates_session()


async def on_shutdown(_):
    await close_rates_session()


async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(cancel.router)
    dp.include_router(menu_navigation.router)
    dp.include_router(request.router)
    dp.include_router(faq.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

