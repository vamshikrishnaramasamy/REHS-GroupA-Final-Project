# Detection Alerts: Notification Channel Comparison (Issue 9, Task 1)

## Options considered

| Channel | Cost | Setup complexity | Privacy footprint |
|---|---|---|---|
| SMS (Twilio) | ~$0.0079/text + ~$1/mo number rental | Medium — Twilio account, verified number, API keys | Stores phone numbers (PII) |
| Push (Firebase/OneSignal) | Free tier generous | High for us specifically — requires a mobile app or PWA to register device tokens, which we don't have yet | Stores device tokens |
| **Email (SMTP/SendGrid)** | **$0** via Gmail SMTP (500/day) or SendGrid free tier (100/day) | **Low** — no client app needed | Stores email addresses (PII) |

## Decision

Going with **email**. We don't have a mobile app or PWA yet, so push would require building app infrastructure just to receive alerts. SMS works today but adds recurring cost and an external vendor (Twilio) for no real benefit at this stage. Email is free, needs no client app, and reuses infrastructure (SMTP) every team member already understands.

## Cost

$0 for this scope, using Gmail SMTP's free tier (500 emails/day limit). If detection volume grows past that, SendGrid's free tier (100/day) or paid tier is the next step — no code change required beyond swapping SMTP host/credentials.

## Setup steps

1. Use (or create) a Gmail account dedicated to sending alerts.
2. Enable 2-Step Verification on that account (required before Google will issue App Passwords).
3. Generate an App Password: Google Account → Security → 2-Step Verification → App passwords. Create one for "Mail".
4. Copy `.env.example` to `.env` and fill in:
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USER=<the Gmail address>`
   - `SMTP_APP_PASSWORD=<the generated app password>`
   - `ALERT_RECIPIENT=<address that should receive alerts>`
5. Install dependencies (`pip install -r requirements.txt`) so `python-dotenv` is available.
6. Never commit `.env` — it's in `.gitignore`. Only `.env.example` (no real values) is tracked.

## Privacy concerns

- Alert emails contain a person's name plus detection metadata (camera name, confidence score, timestamp). This is personal data and should be handled like any other PII: don't paste real names or real test subjects' data into commits, issues, or screenshots shared outside the team.
- Consider whether the **detected person** needs to consent to being notified about, or to having their detection reported to a third party (the alert recipient) — this is a "detection alert" of a person's presence, not just a notification to the system owner. Depending on deployment context (e.g. a home vs. a shared/public space) this may raise separate consent/notice obligations beyond the recipient's own privacy.
- Email is sent over TLS (`starttls()`), but is still readable by the recipient's inbox provider and this account's SMTP provider — keep the recipient list restricted to people who need it.
- SMTP credentials (`SMTP_APP_PASSWORD`) are secrets: they live only in `.env`, are excluded from git via `.gitignore`, and should be rotated if ever exposed.
