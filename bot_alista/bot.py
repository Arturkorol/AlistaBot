import asyncio
from aiogram import Bot, Dispatcher
from bot_alista.settings import settings
from bot_alista.handlers import menu, calculate, cancel, request, faq
from bot_alista.services.rates import close_rates_session


async def on_shutdown(bot):
    await close_rates_session()


async def main():
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    dp.shutdown.register(on_shutdown)

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(cancel.router)
    dp.include_router(request.router)
    dp.include_router(faq.router)

    # Ensure polling works even if a webhook was previously configured
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        # Ignore if no webhook configured or network hiccup; polling should still proceed
        pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


