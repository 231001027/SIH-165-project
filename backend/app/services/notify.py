"""Email / mock delivery for Hi-Po alerts. Never raises into the analysis pipeline."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_hipo_alert(report, assignee, oisd: dict | None, sif: str) -> None:
    """Send (or mock-log) a Hi-Po / HIGH alert. Swallows delivery errors at call site."""
    settings = get_settings()
    oisd = oisd or {}
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reports/{report.id}"
    subject = f"[SIFGuard] Hi-Po/HIGH alert — {report.report_code}"
    body = (
        f"Report: {report.report_code} (id={report.id})\n"
        f"Site: {getattr(report.site, 'name', None) or 'Unknown'}\n"
        f"Activity: {getattr(report.activity, 'name', None) or 'Unknown'}\n"
        f"SIF band: {sif}\n"
        f"OISD band: {oisd.get('band')} | Hi-Po: {oisd.get('is_hipo')}\n"
        f"Rationale: {oisd.get('rationale')}\n"
        f"Life-Saving Rule: (see report detail)\n"
        f"Open: {link}\n"
        f"Action required: Approve / Modify / Reject / Escalate\n"
    )
    mode = (settings.NOTIFY_MODE or "mock").lower().strip()
    if mode == "smtp" and settings.SMTP_HOST:
        _send_smtp(assignee.email, subject, body)
    else:
        # ASCII-safe for Windows consoles (cp1252); rationale may contain arrows etc.
        safe_body = body.replace("\u2192", "->").encode("ascii", errors="replace").decode("ascii")
        logger.info(
            "HIPO_ALERT_MOCK to=%s name=%s subject=%s\n%s",
            assignee.email,
            assignee.person_name,
            subject,
            safe_body,
        )
        print(f"[HIPO_ALERT_MOCK] to={assignee.email} ({assignee.person_name})\n{subject}\n{safe_body}")


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
