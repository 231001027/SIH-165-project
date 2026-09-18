"""End-to-end SIF classification tests via the analysis_service pipeline
(rule engine only -- no ML classifier trained in the test DB, which is itself
an important scenario: the system must produce a full, sensible result using
just the deterministic rule engine, per blueprint Part 7.3 offline guarantee)."""
import itertools
from datetime import datetime, timezone

from app.models.report import Report, ReportType, ReportSource
from app.services.analysis_service import analyze_report

_report_counter = itertools.count(1)


def _analyze(db_session, narrative: str) -> "AnalysisResult":  # noqa: F821
    report = Report(
        report_code=f"TEST-{next(_report_counter)}",
        report_type=ReportType.NEAR_MISS,
        title="Test report",
        narrative=narrative,
        source=ReportSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return analyze_report(db_session, report)


def test_flagship_scenario_is_high_with_evidence(db_session):
    analysis = _analyze(
        db_session,
        "Technician opened a flange before confirming isolation. Residual pressure was released. No injury occurred.",
    )
    assert analysis.sif_classification.value == "HIGH"
    assert analysis.primary_lsr == "Energy Isolation"
    assert "HIGH_ENERGY_SOURCE" in analysis.reason_codes
    assert "CRITICAL_BARRIER_FAILURE" in analysis.reason_codes
    assert analysis.confidence > 0
    assert analysis.explanation_text  # must be non-empty and evidence-based


def test_never_forces_a_binary_yes_no_output(db_session):
    """The system must never collapse to a bare SIF=YES/NO -- it must always
    return one of the defined bands (including explicit UNSUPPORTED_LANGUAGE)."""
    analysis = _analyze(db_session, "A loose cable tie was found on the walkway; corrected on the spot.")
    assert analysis.sif_classification.value in (
        "HIGH", "MEDIUM", "LOW", "NON_SIF", "REVIEW", "UNSUPPORTED_LANGUAGE",
    )


def test_good_practice_report_is_not_flagged_as_a_failure(db_session):
    analysis = _analyze(
        db_session,
        "Isolation was correctly applied, tagged, and verified using a zero-energy check "
        "before the technician began the pump maintenance task.",
    )
    assert analysis.sif_classification.value in ("NON_SIF", "LOW")


def test_no_injury_does_not_mean_low_risk(db_session):
    """Core project thesis: 'no injury occurred' must not automatically drive the
    classification toward NON_SIF/LOW when hazard+exposure+barrier-failure evidence exists."""
    analysis = _analyze(
        db_session,
        "Technician opened a flange before confirming isolation. Residual pressure was released. No injury occurred.",
    )
    assert analysis.sif_classification.value in ("HIGH", "MEDIUM", "REVIEW")
    assert analysis.sif_classification.value != "NON_SIF"


def test_risk_score_breakdown_is_transparent_and_labelled_as_prototype(db_session):
    analysis = _analyze(db_session, "Worker leaned out from a scaffold platform without re-anchoring the fall-arrest lanyard.")
    assert 0 <= analysis.risk_score <= 100
    assert "_disclaimer" in analysis.risk_breakdown
    assert "PROTOTYPE" in analysis.risk_breakdown["_disclaimer"]
    total_components = sum(
        v for k, v in analysis.risk_breakdown.items()
        if k not in ("total", "_disclaimer", "standards_tags", "language_script", "language_abstention", "analysis_status")
        and isinstance(v, (int, float))
    )
    assert abs(total_components - analysis.risk_breakdown["total"]) < 0.5


def test_review_classification_carries_an_abstain_reason(db_session):
    """Whenever the system abstains, it must explain why -- never a silent REVIEW."""
    # A very sparse, ambiguous narrative is likely (not guaranteed) to trigger low confidence.
    analysis = _analyze(db_session, "Near miss reported but activity and location are unclear.")
    if analysis.sif_classification.value == "REVIEW":
        assert analysis.abstain_reason
