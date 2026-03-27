"""
Email delivery configuration for the KešMani Trading Intelligence System.

Reads all credentials from environment variables so no secrets are ever
committed to source control.  Copy .env.example → .env and fill in your
own values before running.
"""

import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_CONFIG: dict[str, str | int] = {
    "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "smtp_user": os.getenv("SMTP_USER", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
    "recipient_email": os.getenv("RECIPIENT_EMAIL", ""),
    "sender_name": "Kesmani Trading Intelligence",
}
