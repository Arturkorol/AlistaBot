import smtplib
from email.mime.text import MIMEText

TOKEN = "8318772952:AAGGMwcRSbbd42YuR-rkUkA53Qf6DHTQJTs"

# В будущем для email
SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
EMAIL_LOGIN = "korol.artur.2002@yandex.ru"
EMAIL_PASSWORD = "attqhdcqxfdkepcm"
EMAIL_TO = "korol.artur.2002@yandex.ru"

msg = MIMEText("Тестовое письмо от бота", "plain", "utf-8")
msg["Subject"] = "Проверка почты"
msg["From"] = EMAIL_LOGIN
msg["To"] = EMAIL_TO

try:
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
        server.sendmail(EMAIL_LOGIN, EMAIL_TO, msg.as_string())
    print("✅ Письмо отправлено!")
except smtplib.SMTPAuthenticationError:
    print("❌ Ошибка авторизации! Проверь логин или пароль приложения.")
except Exception as e:
    print(f"❌ Другая ошибка: {e}")