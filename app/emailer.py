"""Email notification scaffold."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import Config, load_config


logger = logging.getLogger(__name__)


def send_email_report(subject: str, body: str, config: Config | None = None) -> bool:
    """Send the report by email when email is explicitly enabled."""

    config = config or load_config()
    if not config.enable_email:
        logger.info("Email disabled; skipping email report.")
        return False

    missing = [
        name
        for name, value in {
            "SMTP_HOST": config.smtp_host,
            "EMAIL_FROM": config.email_from,
            "EMAIL_TO": config.email_to,
        }.items()
        if not value
    ]
    if missing:
        logger.warning("Email enabled but missing configuration: %s", ", ".join(missing))
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.email_from
    message["To"] = config.email_to
    message.set_content(body)

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if config.smtp_username and config.smtp_password:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
        logger.info("Email report sent to %s.", config.email_to)
        return True
    except Exception:
        logger.exception("Email report failed.")
        return False
