"""Hi-Po / HIGH notification routing: trigger, SMTP non-blocking, review ack."""
from __future__ import annotations

from unittest.mock import patch

from app.models.notification import AssigneeRole, AssigneeRouting, NotificationLog


FLAGSHIP_NARRATIVE = (
    "During pipeline flange maintenance, the technician opened the flange before "
    "confirming isolation and LOTO. Residual pressurized hydrocarbon was released. "
    "PTW was bypassed. No injury occurred but this was a high-potential near miss."
)

SITE_NAME = "Site A (Upstream E&P)"


def _seed_routing(db_session, site: str = SITE_NAME):
    existing = (
        db_session.query(AssigneeRouting)
        .filter(AssigneeRouting.site == site, AssigneeRouting.role == AssigneeRole.SITE_HSE_MANAGER)
        .first()
    )
    if existing:
        return existing
    row = AssigneeRouting(
        site=site,
        role=AssigneeRole.SITE_HSE_MANAGER,
        person_name="Demo HSE Manager A",
        email="hse.manager.a@demo.sifguard.local",
        is_active=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_high_hipo_analysis_creates_notification_log(client, auth_headers, db_session):
    _seed_routing(db_session)
    resp = client.post(
        "/api/reports",
        headers=auth_headers,
        json={
            "report_type": "NEAR_MISS",
            "title": "Flagship LOTO near-miss",
            "narrative": FLAGSHIP_NARRATIVE,
            "site": SITE_NAME,
            "activity": "Pipeline Maintenance",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["analysis"] is not None
    assert body["analysis"]["sif_classification"] == "HIGH"
    oisd = body["analysis"].get("oisd_classification")
    assert oisd is not None
    assert oisd.get("consequence") >= 4 or body["analysis"]["sif_classification"] == "HIGH"

    logs = db_session.query(NotificationLog).filter(NotificationLog.report_id == body["id"]).all()
    assert len(logs) >= 1
    assert logs[0].acknowledged_at is None
    assert "HIGH" in logs[0].band_at_trigger or "HIPO" in logs[0].band_at_trigger

    nresp = client.get(f"/api/reports/{body['id']}/notifications", headers=auth_headers)
    assert nresp.status_code == 200
    assert len(nresp.json()) >= 1


def test_smtp_failure_does_not_block_analysis(client, auth_headers, db_session):
    _seed_routing(db_session)
    with patch("app.services.notify.send_hipo_alert", side_effect=RuntimeError("SMTP down")):
        resp = client.post(
            "/api/reports",
            headers=auth_headers,
            json={
                "report_type": "NEAR_MISS",
                "title": "SMTP fail still analyzes",
                "narrative": FLAGSHIP_NARRATIVE,
                "site": SITE_NAME,
                "activity": "Pipeline Maintenance",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["analysis"] is not None
    assert body["analysis"]["sif_classification"] == "HIGH"
    # Log should still be written before send attempt
    logs = db_session.query(NotificationLog).filter(NotificationLog.report_id == body["id"]).all()
    assert len(logs) >= 1


def test_review_action_acknowledges_notifications(client, auth_headers, db_session):
    _seed_routing(db_session)
    create = client.post(
        "/api/reports",
        headers=auth_headers,
        json={
            "report_type": "NEAR_MISS",
            "title": "Ack on review",
            "narrative": FLAGSHIP_NARRATIVE,
            "site": SITE_NAME,
            "activity": "Pipeline Maintenance",
        },
    )
    assert create.status_code == 200, create.text
    report_id = create.json()["id"]
    logs = db_session.query(NotificationLog).filter(NotificationLog.report_id == report_id).all()
    assert logs
    assert all(l.acknowledged_at is None for l in logs)

    review = client.post(
        f"/api/review/{report_id}",
        headers=auth_headers,
        json={"action": "APPROVE", "reason": "Confirmed Hi-Po near miss"},
    )
    assert review.status_code == 200, review.text

    db_session.expire_all()
    logs = db_session.query(NotificationLog).filter(NotificationLog.report_id == report_id).all()
    assert logs
    assert all(l.acknowledged_at is not None for l in logs)
    assert all(l.acknowledged_action == "APPROVE" for l in logs)

    metrics = client.get("/api/metrics/response-time", headers=auth_headers)
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["overall"]["count"] >= 1
    assert body["overall"]["median_seconds"] is not None
