"""
Email sender for Kesmani.

Sends the HTML daily report via SMTP.  Supports Gmail app passwords
and any standard SMTP provider.

Configuration is read exclusively from environment variables (see .env.example).

Scheduling hint:
  Add a cron job to run the daily report every weekday at 8:00 AM:

  # crontab -e
  0 8 * * 1-5 /path/to/venv/bin/python -c "from src.reports.email_sender import send_daily_report; send_daily_report()" >> /var/log/kesmani.log 2>&1
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config.email_config import EMAIL_CONFIG

logger = logging.getLogger(__name__)


def send_report_email(
    html_body: str,
    subject: Optional[str] = None,
    recipient: Optional[str] = None,
) -> bool:
    """
    Send an HTML email report via SMTP.

    Parameters
    ----------
    html_body:
        Full HTML content of the email body.
    subject:
        Email subject line.  Defaults to a dated report title.
    recipient:
        Recipient address.  Defaults to EMAIL_CONFIG["recipient_email"].

    Returns
    -------
    True if the email was sent successfully, False otherwise.
    """
    smtp_host = EMAIL_CONFIG["smtp_host"]
    smtp_port = EMAIL_CONFIG["smtp_port"]
    smtp_user = EMAIL_CONFIG["smtp_user"]
    smtp_password = EMAIL_CONFIG["smtp_password"]
    recipient = recipient or EMAIL_CONFIG["recipient_email"]

    if not smtp_user or not smtp_password:
        logger.warning(
            "Email credentials not configured.  Set SMTP_USER and SMTP_PASSWORD in .env"
        )
        return False

    if not recipient:
        logger.warning("No recipient email configured.")
        return False

    if subject is None:
        subject = f"Kesmani Daily Brief — {datetime.now().strftime('%A, %B %d, %Y')}"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{EMAIL_CONFIG['sender_name']} <{smtp_user}>"
        msg["To"] = recipient

        # Plain-text fallback
        plain_text = "Please view this email in an HTML-capable email client."
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient, msg.as_string())

        logger.info("Daily report emailed to %s", recipient)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed.  Check SMTP_USER/SMTP_PASSWORD.  "
            "For Gmail, use an App Password (not your main password)."
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error sending email: %s", exc)
        return False


def send_daily_report(account_size: Optional[float] = None) -> bool:
    """
    Build and send the daily report in one call.

    Convenience wrapper that builds the report, formats it to HTML,
    and sends it via email.

    Returns
    -------
    True if sent successfully.
    """
    from src.reports.daily_report import build_daily_report, format_html_report

    try:
        report = build_daily_report(account_size=account_size)
        html = format_html_report(report)
        return send_report_email(html)
    except Exception as exc:
        logger.error("Failed to send daily report: %s", exc)
        return False
