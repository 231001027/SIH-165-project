"""Hi-Po / HIGH notification routing and acknowledgment."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, SifClassification
from app.models.notification import AssigneeRole, AssigneeRouting, NotificationLog
from app.models.report import Report
from app.services.notify import send_hipo_alert

logger = logging.getLogger(__name__)


def _resolve_assignee(db: Session, site_name: str | None) -> AssigneeRouting | None:
    if not site_name:
        return None
    manager = (
        db.query(AssigneeRouting)
        .filter(
            AssigneeRouting.site == site_name,
            AssigneeRouting.role == AssigneeRole.SITE_HSE_MANAGER,
            AssigneeRouting.is_active == True,  # noqa: E712
        )
        .first()
    )
    if manager:
        return manager
    return (
        db.query(AssigneeRouting)
        .filter(
            AssigneeRouting.site == site_name,
            AssigneeRouting.role == AssigneeRole.SITE_HSE_OFFICER,
            AssigneeRouting.is_active == True,  # noqa: E712
        )
        .first()
    )


def maybe_notify_hipo(db: Session, report: Report, analysis: AnalysisResult) -> NotificationLog | None:
    """After analysis persist: notify if OISD Hi-Po or SIF HIGH. Never raises."""
    try:
        if analysis.sif_classification == SifClassification.UNSUPPORTED_LANGUAGE:
            return None
        oisd = analysis.oisd_classification or {}
        sif_val = analysis.sif_classification.value if hasattr(analysis.sif_classification, "value") else str(analysis.sif_classification)
        is_hipo = bool(oisd.get("is_hipo"))
        if not is_hipo and sif_val != "HIGH":
            return None

        site_name = report.site.name if report.site else None
        assignee = _resolve_assignee(db, site_name)
        if not assignee:
            logger.warning("No active assignee for site=%r — skipping Hi-Po notify", site_name)
            return None

        band = oisd.get("band") or sif_val
        if is_hipo:
            band_at = f"HIPO/{band}"
        else:
            band_at = f"SIF/{sif_val}"

        log = NotificationLog(
            report_id=report.id,
            assignee_id=assignee.id,
            band_at_trigger=band_at,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        try:
            send_hipo_alert(report, assignee, oisd, sif_val)
        except Exception as exc:
            logger.warning("Hi-Po email delivery failed (analysis already saved): %s", exc)

        return log
    except Exception as exc:
        logger.warning("maybe_notify_hipo failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def acknowledge_notifications(db: Session, report_id: int, action: str) -> int:
    """Stamp open notification_log rows for this report on review action."""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.report_id == report_id,
            NotificationLog.acknowledged_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.acknowledged_at = now
        row.acknowledged_action = action
    if rows:
        db.commit()
    return len(rows)


def response_time_metrics(db: Session) -> dict:
    """Mean/median seconds from sent_at to acknowledged_at (real numbers or null)."""
    rows = (
        db.query(NotificationLog, Report)
        .join(Report, Report.id == NotificationLog.report_id)
        .filter(NotificationLog.acknowledged_at.isnot(None))
        .all()
    )
    durations: list[float] = []
    by_site: dict[str, list[float]] = {}
    for log, report in rows:
        sent = log.sent_at
        ack = log.acknowledged_at
        if sent is None or ack is None:
            continue
        # Normalize naive datetimes
        if sent.tzinfo is None:
            sent = sent.replace(tzinfo=timezone.utc)
        if ack.tzinfo is None:
            ack = ack.replace(tzinfo=timezone.utc)
        secs = (ack - sent).total_seconds()
        if secs < 0:
            continue
        durations.append(secs)
        site = report.site.name if report.site else "Unknown"
        by_site.setdefault(site, []).append(secs)

    def _stats(vals: list[float]) -> dict:
        if not vals:
            return {"count": 0, "mean_seconds": None, "median_seconds": None}
        s = sorted(vals)
        n = len(s)
        mid = n // 2
        median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
        return {
            "count": n,
            "mean_seconds": round(sum(s) / n, 1),
            "median_seconds": round(median, 1),
        }

    return {
        "overall": _stats(durations),
        "by_site": {site: _stats(vals) for site, vals in sorted(by_site.items())},
    }
