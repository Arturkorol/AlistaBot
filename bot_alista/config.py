import os

from dotenv import load_dotenv, find_dotenv

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
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Optional: other modules may import this file without a configured token.
# The bot itself validates the presence of the token at startup.
