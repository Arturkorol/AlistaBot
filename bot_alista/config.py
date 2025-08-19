import os
import re

from dotenv import find_dotenv, load_dotenv

# Attempt to load environment variables from a file. If the ENV_FILE
# variable is set, use it; otherwise search for a ".env" file in the
# current working directory tree. Missing files are ignored so that
# configuration can also be supplied via the server environment.
env_file = os.getenv("ENV_FILE")
if env_file:
    load_dotenv(env_file)
else:
    load_dotenv(find_dotenv())

TOKEN = os.getenv("BOT_TOKEN")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
except ValueError:  # Non-integer port
    SMTP_PORT = None
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


def validate_config() -> None:
    """Ensure required settings are present and correctly formatted.

    Raises:
        RuntimeError: If any required configuration value is missing or
            malformed.
    """

    missing = []

    if not TOKEN or not _TOKEN_RE.match(TOKEN):
        missing.append("BOT_TOKEN")

    if not SMTP_SERVER:
        missing.append("SMTP_SERVER")

    if SMTP_PORT is None or SMTP_PORT <= 0:
        missing.append("SMTP_PORT")

    if not EMAIL_LOGIN or not _EMAIL_RE.match(EMAIL_LOGIN):
        missing.append("EMAIL_LOGIN")

    if not EMAIL_PASSWORD:
        missing.append("EMAIL_PASSWORD")

    if not EMAIL_TO or not _EMAIL_RE.match(EMAIL_TO):
        missing.append("EMAIL_TO")

    if missing:
        raise RuntimeError(
            f"Invalid or missing configuration for: {', '.join(missing)}"
        )


# Optional: other modules may import this file without a configured token.
# validate_config() should be called before features that require these
# settings are used.
