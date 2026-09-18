"""Precursor comparison returns shared fields with evidence spans."""
from datetime import datetime, timezone

from app.models.catalog import Site, Activity
from app.models.report import Report, ReportType, ReportSource
from app.services.analysis_service import analyze_report
from app.services.comparison_service import compare_precursors


def _mk(db, code, narrative, title="t"):
    site = db.query(Site).first()
    if not site:
        site = Site(name="Site A", region="R")
        db.add(site)
        db.flush()
    act = db.query(Activity).first()
    if not act:
        act = Activity(name="Maintenance")
        db.add(act)
        db.flush()
    r = Report(
        report_code=code,
        report_type=ReportType.NEAR_MISS,
        title=title,
        narrative=narrative,
        site_id=site.id,
        activity_id=act.id,
        source=ReportSource.MANUAL,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    analyze_report(db, r)
    return r


def test_comparison_shared_field_has_evidence_spans(db_session):
    n1 = (
        "Worker opened a pressurized flange before confirming isolation. "
        "LOTO was not verified and residual energy released near the separator."
    )
    n2 = (
        "Technician cracked a flange joint without verifying LOTO isolation. "
        "Stored pressure released; energy isolation barrier was missing."
    )
    a = _mk(db_session, "CMP-A", n1)
    b = _mk(db_session, "CMP-B", n2)
    result = compare_precursors(db_session, a.id, b.id)
    shared = [f for f in result["fields"] if f["shared"]]
    assert shared, "expected at least one shared precursor field"
    assert any(f.get("query_evidence") and f.get("match_evidence") for f in shared)
    assert result["query_narrative"] and result["match_narrative"]
