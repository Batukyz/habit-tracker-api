import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("habit_tracker_api")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@habit-tracker.local")


def send_email(to: str, subject: str, body: str) -> None:
    """Sends via SMTP if configured; otherwise logs the email (dev fallback, sends nothing)."""
    if not SMTP_HOST:
        logger.info("Email not sent (no SMTP_HOST configured) to=%s subject=%r\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)


def send_password_reset_email(to: str, token: str) -> None:
    send_email(
        to=to,
        subject="Habit Tracker API - Şifre sıfırlama",
        body=(
            f"Şifreni sıfırlamak için bu token'ı kullan: {token}\n"
            "Bu token 60 dakika geçerlidir ve yalnızca bir kez kullanılabilir.\n"
            "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin."
        ),
    )
