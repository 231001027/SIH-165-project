"""Trend / Pattern Engine (blueprint Part 1.3 Stage 14, Part 6.1 'What changed?').
All statistics here are computed directly from the current database contents
-- never fabricated -- and period-over-period "what changed" statements are
explicitly labelled as an observed correlation, never a stated cause, per
Part 6.1."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult, SifClassification
from app.models.report import Report, ReportSource
from app.models.catalog import Site

MIN_SAMPLE_FOR_WHAT_CHANGED = 5


def sif_trend_over_time(db: Session) -> list[dict]:
    rows = (
        db.query(Report.occurred_at, AnalysisResult.sif_classification)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for occurred_at, classification in rows:
        month_key = occurred_at.strftime("%Y-%m") if occurred_at else "unknown"
        buckets[month_key][classification.value if hasattr(classification, "value") else classification] += 1
        buckets[month_key]["TOTAL"] += 1

    result = []
    for month in sorted(buckets.keys()):
        b = buckets[month]
        result.append({
            "month": month,
            "total": b.get("TOTAL", 0),
            "high": b.get("HIGH", 0),
            "medium": b.get("MEDIUM", 0),
            "low": b.get("LOW", 0),
            "non_sif": b.get("NON_SIF", 0),
            "review": b.get("REVIEW", 0),
        })
    return result


def lsr_distribution(db: Session) -> list[dict]:
    rows = (
        db.query(AnalysisResult.primary_lsr, AnalysisResult.sif_classification)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(
            AnalysisResult.sif_classification.in_([SifClassification.HIGH, SifClassification.MEDIUM]),
            Report.source != ReportSource.PUBLIC_CORPUS,
        )
        .all()
    )
    counts: dict[str, int] = defaultdict(int)
    for lsr, _ in rows:
        counts[lsr or "No applicable rule"] += 1
    return [{"lsr": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


def lsr_distribution_by_site(db: Session) -> dict:
    """Cross-site LSR comparison (blueprint Part 4.2). Returns a row per site
    with a count per LSR, shaped for a stacked/grouped bar chart, plus the flat
    list of LSR names actually present so the frontend can build a consistent
    series/legend without guessing which keys exist."""
    from app.models.analysis import ReportBarrier  # noqa: F401  (keep import grouping consistent)

    rows = (
        db.query(Site.name, AnalysisResult.primary_lsr)
        .select_from(Report)
        .join(Site, Site.id == Report.site_id)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .filter(
            AnalysisResult.sif_classification.in_([SifClassification.HIGH, SifClassification.MEDIUM]),
            Report.source != ReportSource.PUBLIC_CORPUS,
        )
        .all()
    )
    per_site: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    all_lsrs: set[str] = set()
    for site_name, lsr in rows:
        lsr_name = lsr or "No applicable rule"
        per_site[site_name][lsr_name] += 1
        all_lsrs.add(lsr_name)

    lsr_order = sorted(all_lsrs)
    series = []
    for site_name, counts in sorted(per_site.items()):
        row = {"site": site_name}
        row.update({lsr: counts.get(lsr, 0) for lsr in lsr_order})
        series.append(row)
    return {"lsr_names": lsr_order, "series": series}


def barrier_failure_distribution(db: Session) -> list[dict]:
    from app.models.analysis import ReportBarrier

    rows = (
        db.query(ReportBarrier.barrier_type, ReportBarrier.status)
        .join(AnalysisResult, AnalysisResult.id == ReportBarrier.analysis_id)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    counts: dict[tuple, int] = defaultdict(int)
    for barrier_type, status in rows:
        status_val = status.value if hasattr(status, "value") else status
        if status_val == "PRESENT_EFFECTIVE":
            continue
        counts[(barrier_type, status_val)] += 1
    result = [{"barrier": k[0], "status": k[1], "count": v} for k, v in counts.items()]
    result.sort(key=lambda r: -r["count"])
    return result


def hazard_energy_distribution(db: Session) -> dict:
    hazard_rows = (
        db.query(AnalysisResult.hazard)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(AnalysisResult.hazard.isnot(None), Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    energy_rows = (
        db.query(AnalysisResult.energy_category)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(AnalysisResult.energy_category.isnot(None), Report.source != ReportSource.PUBLIC_CORPUS)
        .all()
    )
    hazard_counts: dict[str, int] = defaultdict(int)
    for (h,) in hazard_rows:
        hazard_counts[h] += 1
    energy_counts: dict[str, int] = defaultdict(int)
    for (e,) in energy_rows:
        energy_counts[e] += 1
    return {
        "hazards": [{"hazard": k, "count": v} for k, v in sorted(hazard_counts.items(), key=lambda kv: -kv[1])],
        "energy_sources": [{"energy_category": k, "count": v} for k, v in sorted(energy_counts.items(), key=lambda kv: -kv[1])],
    }


def what_changed(db: Session) -> list[dict]:
    """Period-over-period % change per LSR between the two most recent
    calendar months present in the data, gated by a minimum-sample threshold."""
    rows = (
        db.query(Report.occurred_at, AnalysisResult.primary_lsr, AnalysisResult.sif_classification)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .filter(
            AnalysisResult.sif_classification.in_([SifClassification.HIGH, SifClassification.MEDIUM]),
            Report.source != ReportSource.PUBLIC_CORPUS,
        )
        .all()
    )
    if not rows:
        return []

    months = sorted({r[0].strftime("%Y-%m") for r in rows if r[0]})
    if len(months) < 2:
        return []
    prev_month, latest_month = months[-2], months[-1]

    prev_counts: dict[str, int] = defaultdict(int)
    latest_counts: dict[str, int] = defaultdict(int)
    for occurred_at, lsr, _ in rows:
        if not occurred_at:
            continue
        key = occurred_at.strftime("%Y-%m")
        if key == prev_month:
            prev_counts[lsr or "No applicable rule"] += 1
        elif key == latest_month:
            latest_counts[lsr or "No applicable rule"] += 1

    statements = []
    all_lsrs = set(prev_counts) | set(latest_counts)
    for lsr in all_lsrs:
        prev_n = prev_counts.get(lsr, 0)
        latest_n = latest_counts.get(lsr, 0)
        if prev_n + latest_n < MIN_SAMPLE_FOR_WHAT_CHANGED:
            continue
        if prev_n == 0:
            continue
        pct_change = round(((latest_n - prev_n) / prev_n) * 100, 1)
        if abs(pct_change) < 15:
            continue
        direction = "increased" if pct_change > 0 else "decreased"
        statements.append({
            "lsr": lsr,
            "previous_month": prev_month,
            "latest_month": latest_month,
            "previous_count": prev_n,
            "latest_count": latest_n,
            "pct_change": pct_change,
            "statement": (
                f"{lsr} precursor reports {direction} {abs(pct_change)}% from {prev_month} to "
                f"{latest_month} ({prev_n} -> {latest_n} reports). This is an observed correlation "
                f"in the current dataset, not an inferred cause."
            ),
        })
    statements.sort(key=lambda s: -abs(s["pct_change"]))
    return statements
