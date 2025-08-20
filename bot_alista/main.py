"""Entry point for running the Telegram bot."""

import argparse
import asyncio
import logging
import sys

from .bot import main as run_bot
from .config import validate_config

logging.basicConfig(level=logging.INFO)


def main(argv: list[str] | None = None) -> None:
    """Run the bot and report missing configuration."""
    parser = argparse.ArgumentParser(description="Run the Telegram bot")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Override existing lock file for emergency restarts",
    )
    args = parser.parse_args(argv)

    try:
        validate_config()
        asyncio.run(run_bot(force=args.force))
    except RuntimeError as exc:  # Missing configuration or lock error
        logging.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
