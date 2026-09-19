"""Review action semantics: APPROVE / MODIFY / REJECT / ESCALATE."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.analysis import AnalysisResult, SifClassification
from app.models.report import Report, ReportSource, ReportType
from app.models.review import FORBIDDEN_ESCALATE_REASONS


def _seed_reviewable(db_session, analyst_user, code: str = "REV-TEST-1"):
    report = Report(
        report_code=code,
        report_type=ReportType.NEAR_MISS,
        title="Review semantics test",
        narrative="Technician opened a flange before confirming isolation. Residual pressure released.",
        source=ReportSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(report)
    db_session.flush()
    analysis = AnalysisResult(
        report_id=report.id,
        sif_classification=SifClassification.HIGH,
        confidence=88.0,
        review_required=True,
        risk_score=70.0,
        risk_breakdown={},
        reason_codes=["HIGH_ENERGY_SOURCE"],
        primary_lsr="Energy Isolation",
        hazard="Stored / pressurized energy",
        energy_source="Pressurized fluid",
        exposure_proximity="HIGH",
        potential_consequence="Serious injury / fatality",
        explanation_text="Flagged as HIGH.",
        explanation_source="template",
        original_prediction={
            "sif_classification": "HIGH",
            "confidence": 88.0,
            "primary_lsr": "Energy Isolation",
            "hazard": "Stored / pressurized energy",
        },
    )
    db_session.add(analysis)
    db_session.commit()
    return report, analysis


def test_approve_clears_queue_keeps_classification(client, auth_headers, db_session, analyst_user):
    report, analysis = _seed_reviewable(db_session, analyst_user, "REV-APPROVE-1")
    before = analysis.sif_classification.value
    resp = client.post(
        f"/api/review/{report.id}",
        headers=auth_headers,
        json={"action": "APPROVE", "reason": "Looks correct"},
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(analysis)
    assert analysis.review_required is False
    assert analysis.sif_classification.value == before


def test_reject_clears_queue_without_changing_classification(client, auth_headers, db_session, analyst_user):
    report, analysis = _seed_reviewable(db_session, analyst_user, "REV-REJECT-1")
    before = analysis.sif_classification.value
    resp = client.post(
        f"/api/review/{report.id}",
        headers=auth_headers,
        json={"action": "REJECT", "reason": "Duplicate of another ticket"},
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(analysis)
    assert analysis.review_required is False
    assert analysis.sif_classification.value == before


def test_modify_updates_classification_preserves_original_snapshot(client, auth_headers, db_session, analyst_user):
    report, analysis = _seed_reviewable(db_session, analyst_user, "REV-MODIFY-1")
    snap_before = dict(analysis.original_prediction)
    resp = client.post(
        f"/api/review/{report.id}",
        headers=auth_headers,
        json={
            "action": "MODIFY",
            "reason": "Over-classified; barrier was verified",
            "corrected_fields": {"sif_classification": "MEDIUM"},
        },
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(analysis)
    assert analysis.review_required is False
    assert analysis.sif_classification.value == "MEDIUM"
    assert analysis.original_prediction == snap_before
    assert analysis.original_prediction["sif_classification"] == "HIGH"


def test_escalate_requires_nonempty_nondefault_reason(client, auth_headers, db_session, analyst_user):
    report, analysis = _seed_reviewable(db_session, analyst_user, "REV-ESC-1")
    for bad in FORBIDDEN_ESCALATE_REASONS:
        resp = client.post(
            f"/api/review/{report.id}",
            headers=auth_headers,
            json={"action": "ESCALATE", "reason": bad},
        )
        assert resp.status_code == 422, bad

    resp = client.post(
        f"/api/review/{report.id}",
        headers=auth_headers,
        json={"action": "ESCALATE", "reason": "Needs site superintendent sign-off on LOTO process"},
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(analysis)
    assert analysis.review_required is True
    assert "Needs site superintendent" in (analysis.abstain_reason or "")
