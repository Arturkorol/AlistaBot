"""Entry point for running the Telegram bot."""

import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append(os.path.dirname(__file__))
from bot_alista.bot import main as run_bot


if __name__ == "__main__":
    asyncio.run(run_bot())
