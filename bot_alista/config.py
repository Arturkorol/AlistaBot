import os
from pathlib import Path

from dotenv import load_dotenv

# Load the .env file located in the project root regardless of the
# current working directory. This avoids situations where environment
# variables are not loaded when the script is executed from another
# folder.
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

TOKEN = os.getenv("BOT_TOKEN")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# Optional: other modules may import this file without a configured token.
# The bot itself validates the presence of the token at startup.
