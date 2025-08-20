"""Bot startup and locking utilities."""

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

import os
import atexit
import logging

from .config import TOKEN
from .handlers import menu, calculate, navigation, request

LOCKFILE = "/tmp/alistabot.lock"


def _remove_lock() -> None:
    try:
        os.remove(LOCKFILE)
    except OSError:
        pass


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _acquire_lock(force: bool) -> None:
    """Create a lock file to prevent multiple polling processes.

    The lock file contains the PID of the owning process. Creation uses an
    atomic operation so that two processes cannot acquire the lock
    simultaneously. If a lock already exists and ``force`` is ``True`` the PID
    from the file is checked and the lock is removed only if no such process is
    running.
    """

    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if not force:
            raise RuntimeError(
                f"Another instance appears to be running (lock: {LOCKFILE})."
            )
        pid = None
        try:
            with open(LOCKFILE) as existing:
                pid = int(existing.read().strip())
        except Exception:
            pass
        if pid is not None and _pid_running(pid):
            raise RuntimeError(
                f"Another instance (PID {pid}) appears to be running (lock: {LOCKFILE})."
            )
        _remove_lock()
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

    with os.fdopen(fd, "w") as lock:
        lock.write(str(os.getpid()))

    atexit.register(_remove_lock)


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

    try:
        await dp.start_polling(bot)
    except TelegramConflictError:
        logging.error(
            "Telegram reported a conflict: another bot instance may be running."
        )
        raise SystemExit(1)
