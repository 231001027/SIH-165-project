from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import AnalysisResult, SifClassification, PrecursorCluster, ReportBarrier
from app.models.report import Report, ReportSource
from app.models.user import User
from app.services import trend_service, ranking_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # PUBLIC_CORPUS rows are real historical incidents kept only to ground similarity
    # search (see similarity_service.py) -- every KPI/aggregate here must describe
    # OIL's own (synthetic-demo or user-submitted) reports only.
    not_reference = Report.source != ReportSource.PUBLIC_CORPUS
    own_reports = db.query(Report).filter(not_reference)
    total_reports = own_reports.count()

    def analyzed_where(*extra):
        q = (
            db.query(AnalysisResult)
            .join(Report, Report.id == AnalysisResult.report_id)
            .filter(not_reference)
        )
        for clause in extra:
            q = q.filter(clause)
        return q.count()

    total_analyzed = analyzed_where()

    def count_where(classification):
        return analyzed_where(AnalysisResult.sif_classification == classification)

    high = count_where(SifClassification.HIGH)
    medium = count_where(SifClassification.MEDIUM)
    low = count_where(SifClassification.LOW)
    non_sif = count_where(SifClassification.NON_SIF)
    review = count_where(SifClassification.REVIEW)
    review_queue = analyzed_where(AnalysisResult.review_required == True)  # noqa: E712
    repeat_precursors = analyzed_where(AnalysisResult.repeat_precursor_count >= 2)
    critical_barrier_failures = (
        db.query(ReportBarrier)
        .join(AnalysisResult, AnalysisResult.id == ReportBarrier.analysis_id)
        .join(Report, Report.id == AnalysisResult.report_id)
        .filter(not_reference, ReportBarrier.status.in_(["FAILED", "BYPASSED", "MISSING"]))
        .count()
    )
    sites_affected = own_reports.filter(Report.site_id.isnot(None)).with_entities(Report.site_id).distinct().count()

    return {
        "total_reports": total_reports,
        "total_analyzed": total_analyzed,
        "sif_high": high,
        "sif_medium": medium,
        "sif_low": low,
        "non_sif": non_sif,
        "review_queue_classified_review": review,
        "review_queue_total": review_queue,
        "repeat_precursor_reports": repeat_precursors,
        "critical_barrier_failures": critical_barrier_failures,
        "sites_affected": sites_affected,
    }


@router.get("/trends")
def trends(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {
        "sif_trend": trend_service.sif_trend_over_time(db),
        "what_changed": trend_service.what_changed(db),
    }


@router.get("/lsr")
def lsr_distribution(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return trend_service.lsr_distribution(db)


@router.get("/barriers")
def barriers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return trend_service.barrier_failure_distribution(db)


@router.get("/hazards")
def hazards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return trend_service.hazard_energy_distribution(db)


@router.get("/sites")
def sites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"ranking": ranking_service.site_ranking(db), "caveat": ranking_service.DENOMINATOR_CAVEAT}


@router.get("/activities")
def activities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"ranking": ranking_service.activity_ranking(db), "caveat": ranking_service.DENOMINATOR_CAVEAT}


@router.get("/heatmap")
def site_activity_heatmap(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Site x Activity SIF-precursor density matrix (blueprint Part 6.1 'Site &
    activity risk heatmap'). Same density definition and denominator caveat as
    the site/activity ranking endpoints -- this is a different view of the same
    underlying numbers, not a separate metric."""
    return {"matrix": ranking_service.site_activity_matrix(db), "caveat": ranking_service.DENOMINATOR_CAVEAT}


@router.get("/lsr-by-site")
def lsr_by_site(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cross-site comparison of IOGP Life-Saving Rule distribution among
    SIF-positive (HIGH/MEDIUM) reports (blueprint Part 4.2 'Cross-site LSR trend
    comparison')."""
    return trend_service.lsr_distribution_by_site(db)


@router.get("/clusters")
def clusters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PrecursorCluster).order_by(PrecursorCluster.member_count.desc()).all()
    return [
        {
            "id": c.id, "label": c.label, "method": c.method, "member_count": c.member_count,
            "top_terms": c.top_terms, "dominant_lsr": c.dominant_lsr, "dominant_site": c.dominant_site,
        }
        for c in rows
    ]


@router.get("/clusters/{cluster_id}/members")
def cluster_members(cluster_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.analysis import PrecursorFingerprint
    fps = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.cluster_id == cluster_id).all()
    return [fp.fingerprint_json for fp in fps]
