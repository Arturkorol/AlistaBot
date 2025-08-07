"""Entry point for running the Telegram bot."""

import asyncio

from bot_alista.bot import main as run_bot


if __name__ == "__main__":
    asyncio.run(run_bot())
