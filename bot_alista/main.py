"""Entry point for running the Telegram bot."""

import asyncio
import logging

from .bot import main as run_bot

logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    asyncio.run(run_bot())
