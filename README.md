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

## Customs and duty calculations

- Customs value can now be entered in EUR / USD / JPY / CNY. CBR daily rates are fetched by declaration date; if unavailable, the bot asks for manual rates.
- Import duty minimal threshold is 0.44 EUR/cc; we convert it by the EUR CBR rate on the declaration date.
- To adjust UTIL coefficients, edit `UTIL_CONFIG` in `bot_alista/tariff/util_fee.py`.
- Rules are loaded from `bot_alista/data/rules/russia_auto_import_rules_2025_formulas.csv` (UTF-8-SIG). If the file is missing, minimal fallback rules are used.
- Individuals (personal): STP unified duty from CSV; VAT and excise are embedded.
- Companies (commercial): duty = max(ad valorem, min €/cc) or specific €/cc, plus excise (rub/hp) and VAT 20%.
- Clearance fee ladder updated for 2025 bands.
- Utilization fee uses factual age from production year; for FL duty bucket, the user selects ≤3 or >3 years.

