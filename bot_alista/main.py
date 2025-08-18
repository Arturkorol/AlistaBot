"""Entry point for running the Telegram bot."""

import asyncio
import logging

# When the module is executed as ``python -m bot_alista.main`` the
# package-relative import below works.  However, when run directly as a
# script (e.g. ``python bot_alista/main.py``) the relative import fails.
# To make local development and "run" buttons in editors work, fall back
# to an absolute import in that scenario.
if __package__:
    from .bot import main as run_bot
else:  # pragma: no cover - executed when running as a script
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from bot_alista.bot import main as run_bot

logging.basicConfig(level=logging.INFO)


def main() -> None:
    """Run the bot and report missing configuration."""
    try:
        asyncio.run(run_bot())
    except RuntimeError as exc:  # Missing configuration
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
