"""Entry point for running the Telegram bot."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from bot_alista.bot import main as run_bot


if __name__ == "__main__":
    asyncio.run(run_bot())
