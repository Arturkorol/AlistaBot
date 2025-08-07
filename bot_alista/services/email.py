import os
import smtplib
import ssl

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import EMAIL_LOGIN, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT


def send_email(
    to_email: str, subject: str, body: str, attachment_path: str | None = None
) -> bool:
    """Send an email with optional PDF attachment.

    Returns True if the message was sent successfully, otherwise False.
    """

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_LOGIN
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(attachment_path),
                )
                msg.attach(attach)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email отправлен на {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ Ошибка авторизации SMTP. Проверьте логин/пароль.")
        return False
    except Exception as e:  # pragma: no cover - we just log and return
        print(f"❌ Ошибка отправки письма: {e}")
        return False

        server.sendmail(EMAIL_LOGIN, EMAIL_TO, msg.as_string())
