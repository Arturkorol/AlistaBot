"""Entry point for running the Telegram bot."""

import asyncio
import logging
import os

level_name = os.getenv("LOG_LEVEL", "INFO").upper()
level = getattr(logging, level_name, logging.INFO)
logging.basicConfig(level=level)

from bot_alista.bot import main as run_bot


if __name__ == "__main__":
    asyncio.run(run_bot())
