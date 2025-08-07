# AlistaBot

## Configuration

The bot reads configuration from environment variables. Create a `.env` file using `.env.example` as a template and fill in your values:

```
cp .env.example .env
# edit .env
```

Required variables:

- `BOT_TOKEN` – Telegram bot token.
- `SMTP_SERVER` – SMTP server host.
- `SMTP_PORT` – SMTP port.
- `EMAIL_LOGIN` – SMTP account username.
- `EMAIL_PASSWORD` – SMTP account password.
- `EMAIL_TO` – recipient email address.

Install dependencies and run the bot:

```
pip install -r requirements.txt
python bot_alista/main.py
```

The project uses [`python-dotenv`](https://pypi.org/project/python-dotenv/) to load variables from the `.env` file automatically. For container deployments, supply the same environment variables via your container runtime's secret or environment management instead of a `.env` file.

