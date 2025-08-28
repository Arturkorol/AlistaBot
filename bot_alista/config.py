from __future__ import annotations

from .settings import settings

TOKEN = settings.BOT_TOKEN
SMTP_SERVER = settings.SMTP_SERVER
SMTP_PORT = settings.SMTP_PORT
EMAIL_LOGIN = settings.EMAIL_LOGIN
EMAIL_PASSWORD = settings.EMAIL_PASSWORD
EMAIL_TO = settings.EMAIL_TO

__all__ = [
    "TOKEN",
    "SMTP_SERVER",
    "SMTP_PORT",
    "EMAIL_LOGIN",
    "EMAIL_PASSWORD",
    "EMAIL_TO",
]
