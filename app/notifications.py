import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD")
ALERT_RECIPIENT = os.environ.get("ALERT_RECIPIENT")

PACIFIC = ZoneInfo("America/Los_Angeles")


def _format_pacific(occurred_at: str) -> str:
    """Convert a SQLite CURRENT_TIMESTAMP string (UTC, naive) to Pacific time."""
    utc_dt = datetime.strptime(occurred_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    pacific_dt = utc_dt.astimezone(PACIFIC)
    return pacific_dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")


def send_detection_alert(person_name: str, camera_name: str, confidence: float, occurred_at: str) -> None:
    """Email an alert for a single detection event.

    Raises on failure so callers can decide how to handle it (the detection
    route wraps this in try/except so a broken mail step never blocks logging).
    """
    if not (SMTP_USER and SMTP_APP_PASSWORD and ALERT_RECIPIENT):
        raise RuntimeError(
            "Email alerting is not configured: set SMTP_USER, SMTP_APP_PASSWORD, "
            "and ALERT_RECIPIENT (see .env.example)."
        )

    message = EmailMessage()
    message["Subject"] = f"Security camera alert: {person_name} detected"
    message["From"] = SMTP_USER
    message["To"] = ALERT_RECIPIENT
    message.set_content(
        f"Detection logged.\n\n"
        f"Person: {person_name}\n"
        f"Camera: {camera_name}\n"
        f"Confidence: {confidence}\n"
        f"Occurred at: {_format_pacific(occurred_at)}\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.send_message(message)
