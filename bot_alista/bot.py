"""Bot startup and locking utilities."""

from aiogram import Bot, Dispatcher

import os
import atexit

from .config import TOKEN
from .handlers import menu, calculate, navigation, request

LOCKFILE = "/tmp/alistabot.lock"


def _acquire_lock(force: bool) -> None:
    """Create a lock file to prevent multiple polling processes.

    If the lock file already exists and ``force`` is ``False``, a ``RuntimeError``
    is raised. When ``force`` is ``True`` a stale lock file is removed.
    The lock file is removed automatically at process exit, but if the process
    is killed it might persist and must be deleted manually.
    """

    if os.path.exists(LOCKFILE):
        if force:
            try:
                os.remove(LOCKFILE)
            except OSError:
                pass
        else:
            raise RuntimeError(
                f"Another instance appears to be running (lock: {LOCKFILE})."
            )

    with open(LOCKFILE, "w") as lock:
        lock.write(str(os.getpid()))

    atexit.register(lambda: os.path.exists(LOCKFILE) and os.remove(LOCKFILE))


async def main(*, force: bool = False) -> None:
    """Start polling if the bot token is configured.

    Parameters
    ----------
    force:
        If ``True``, an existing lock file is ignored and replaced.
    """

    _acquire_lock(force)

    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured. Check your environment variables.")
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()

    dp.include_router(menu.router)
    dp.include_router(calculate.router)
    dp.include_router(navigation.router)
    dp.include_router(request.router)

    await dp.start_polling(bot)
