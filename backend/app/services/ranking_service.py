"""Site / Activity SIF-precursor density ranking (blueprint Part 6.2).
Density = SIF-positive reports / total relevant reports for that site or
activity. Raw counts are always returned alongside density, and callers must
display the denominator-limitation caveat (no exposure-hours data available)
-- enforced in the frontend, not silently dropped here."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, SifClassification
from app.models.report import Report, ReportSource
from app.models.catalog import Site, Activity

DENOMINATOR_CAVEAT = (
    "Density is normalized by report volume, not exposure-hours (not available in this "
    "prototype dataset). Treat as a report-volume-normalized indicator, not a true "
    "exposure-normalized risk rate."
)


def _rank(db: Session, group_col, name_lookup: dict[int, str]) -> list[dict]:
    rows = (
        db.query(group_col, AnalysisResult.sif_classification, Report.id)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    totals: dict[int, int] = defaultdict(int)
    sif_positive: dict[int, int] = defaultdict(int)
    high_count: dict[int, int] = defaultdict(int)
    for key, classification, _report_id in rows:
        if key is None:
            continue
        totals[key] += 1
        value = classification.value if hasattr(classification, "value") else classification
        if value in ("HIGH", "MEDIUM"):
            sif_positive[key] += 1
        if value == "HIGH":
            high_count[key] += 1

    ranking = []
    for key, total in totals.items():
        name = name_lookup.get(key, f"#{key}")
        density = round(sif_positive.get(key, 0) / total, 3) if total else 0.0
        ranking.append({
            "name": name,
            "total_reports": total,
            "sif_positive_reports": sif_positive.get(key, 0),
            "high_reports": high_count.get(key, 0),
            "density": density,
        })
    ranking.sort(key=lambda r: (-r["density"], -r["total_reports"]))
    return ranking


def site_ranking(db: Session) -> list[dict]:
    sites = {s.id: s.name for s in db.query(Site).all()}
    return _rank(db, Report.site_id, sites)


def activity_ranking(db: Session) -> list[dict]:
    activities = {a.id: a.name for a in db.query(Activity).all()}
    return _rank(db, Report.activity_id, activities)


def site_activity_matrix(db: Session) -> list[dict]:
    """Site x Activity density matrix for the heatmap view (blueprint Part 6.1).
    One row per (site, activity) combination that has at least one report --
    empty combinations are simply absent rather than padded with zero rows, so
    the frontend heatmap only renders cells with real data."""
    rows = (
        db.query(Site.name, Activity.name, AnalysisResult.sif_classification)
        .select_from(Report)
        .join(Site, Site.id == Report.site_id)
        .join(Activity, Activity.id == Report.activity_id)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    cells: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "sif_positive": 0})
    for site_name, activity_name, classification in rows:
        key = (site_name, activity_name)
        cells[key]["total"] += 1
        value = classification.value if hasattr(classification, "value") else classification
        if value in ("HIGH", "MEDIUM"):
            cells[key]["sif_positive"] += 1

    matrix = []
    for (site_name, activity_name), counts in cells.items():
        density = round(counts["sif_positive"] / counts["total"], 3) if counts["total"] else 0.0
        matrix.append({
            "site": site_name, "activity": activity_name,
            "total_reports": counts["total"], "sif_positive_reports": counts["sif_positive"],
            "density": density,
        })
    matrix.sort(key=lambda r: (-r["density"], -r["total_reports"]))
    return matrix
