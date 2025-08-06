import smtplib
import ssl
import os

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from config import EMAIL_LOGIN, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT, EMAIL_TO

def send_email_with_attachment(to_email: str, subject: str, body: str, attachment_path: str):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_LOGIN
        msg["To"] = to_email
        msg["Subject"] = subject

        # Текст письма
        msg.attach(MIMEText(body, "plain", "utf-8"))

        #Добавляем вложение 
        if attachment_path and os.path.exists(attachment_path):
            
            # Вложение
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header("Content-Disposition", "attachment", 
                                  filename="customs_report.pdf")
                msg.attach(attach)

        #Защищённое соединение
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email отправлен на {to_email}")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print("❌ Ошибка авторизации SMTP. Проверьте логин/пароль.")
        return False
    except Exception as e:
        print(f"❌ Ошибка отправки письма: {e}")
        return False

def send_email(subject: str, body: str, attachment_path: str = None):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_LOGIN
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            attach = MIMEApplication(f.read(), _subtype="pdf")
            attach.add_header("Content-Disposition", "attachment", filename="request.pdf")
            msg.attach(attach)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
        server.sendmail(EMAIL_LOGIN, EMAIL_TO, msg.as_string())