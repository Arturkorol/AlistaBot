"""Entry point for running the Telegram bot."""

import asyncio
import logging
import sys

from .bot import main as run_bot
from .config import validate_config

logging.basicConfig(level=logging.INFO)


def main() -> None:
    """Run the bot and report missing configuration."""
    try:
        validate_config()
        asyncio.run(run_bot())
    except RuntimeError as exc:  # Missing configuration
        logging.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
