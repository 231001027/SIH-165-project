import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_analyst
from app.db.session import get_db
from app.models.analysis import AnalysisResult, SifClassification, ReportBarrier
from app.models.catalog import Site, Activity
from app.models.report import Report, ReportType, ReportSource
from app.models.user import User
from app.schemas.report import (
    ReportCreate, ReportOut, ReportListItem, UploadResult, UploadResultRow, SimilarReportOut,
    PrecursorComparisonOut,
)
from app.services.analysis_service import analyze_report
from app.services.audit_service import log_action
from app.services.similarity_service import find_similar_reports
from app.services.comparison_service import compare_precursors

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _get_or_create_site(db: Session, name: str | None) -> Site | None:
    if not name or not name.strip():
        return None
    name = name.strip()
    site = db.query(Site).filter(Site.name == name).first()
    if not site:
        site = Site(name=name)
        db.add(site)
        db.flush()
    return site


def _get_or_create_activity(db: Session, name: str | None) -> Activity | None:
    if not name or not name.strip():
        return None
    name = name.strip()
    activity = db.query(Activity).filter(Activity.name == name).first()
    if not activity:
        activity = Activity(name=name)
        db.add(activity)
        db.flush()
    return activity


def _next_report_code(db: Session) -> str:
    count = db.query(Report).count()
    return f"OIL-{10000 + count + 1}"


def _create_report_row(db: Session, payload: ReportCreate, source: ReportSource) -> Report:
    if not payload.narrative or not payload.narrative.strip():
        raise ValueError("narrative is required")
    site = _get_or_create_site(db, payload.site)
    activity = _get_or_create_activity(db, payload.activity)
    report = Report(
        report_code=_next_report_code(db),
        report_type=ReportType(payload.report_type) if payload.report_type else ReportType.NEAR_MISS,
        title=payload.title or "",
        narrative=payload.narrative.strip(),
        site_id=site.id if site else None,
        activity_id=activity.id if activity else None,
        location=payload.location,
        reporter_name=payload.reporter_name,
        source=source,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(report)
    db.flush()
    return report


def _serialize_report(report: Report, analysis: AnalysisResult | None) -> ReportOut:
    data = {
        "id": report.id,
        "report_code": report.report_code,
        "report_type": report.report_type.value,
        "title": report.title,
        "narrative": report.narrative,
        "site": report.site.name if report.site else None,
        "activity": report.activity.name if report.activity else None,
        "location": report.location,
        "source": report.source.value,
        "occurred_at": report.occurred_at,
        "created_at": report.created_at,
        "analysis": None,
    }
    if analysis:
        adict = {
            "id": analysis.id,
            "model_version": analysis.model_version,
            "sif_classification": analysis.sif_classification.value,
            "confidence": analysis.confidence,
            "review_required": analysis.review_required,
            "abstain_reason": analysis.abstain_reason,
            "risk_score": analysis.risk_score,
            "risk_breakdown": analysis.risk_breakdown,
            "reason_codes": analysis.reason_codes,
            "primary_lsr": analysis.primary_lsr,
            "primary_lsr_confidence": analysis.primary_lsr_confidence,
            "secondary_lsr": analysis.secondary_lsr,
            "secondary_lsr_confidence": analysis.secondary_lsr_confidence,
            "lsr_evidence": analysis.lsr_evidence,
            "hazard": analysis.hazard,
            "energy_source": analysis.energy_source,
            "energy_category": analysis.energy_category,
            "exposure_description": analysis.exposure_description,
            "exposure_proximity": analysis.exposure_proximity,
            "activity_extracted": analysis.activity_extracted,
            "location_extracted": analysis.location_extracted,
            "potential_consequence": analysis.potential_consequence,
            "explanation_text": analysis.explanation_text,
            "explanation_source": analysis.explanation_source,
            "repeat_precursor_count": analysis.repeat_precursor_count,
            "original_prediction": analysis.original_prediction,
            "barriers": [
                {"barrier_type": b.barrier_type, "status": b.status.value if hasattr(b.status, "value") else b.status,
                 "evidence_text": b.evidence_text, "confidence": b.confidence}
                for b in analysis.barriers
            ],
        }
        data["analysis"] = adict
    return ReportOut.model_validate(data)


@router.post("", response_model=ReportOut)
def create_report(payload: ReportCreate, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    try:
        report = _create_report_row(db, payload, ReportSource.MANUAL)
        db.commit()
        db.refresh(report)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))

    analysis = analyze_report(db, report)
    log_action(db, "REPORT", report.id, "REPORT_CREATED_AND_ANALYZED", user.email,
               {"sif_classification": analysis.sif_classification.value, "report_code": report.report_code})
    return _serialize_report(report, analysis)


@router.post("/upload", response_model=UploadResult)
def upload_reports(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only .csv files are supported.")

    raw = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))

    rows_out: list[UploadResultRow] = []
    successful = 0
    failed = 0
    duplicates = 0
    seen_narratives: set[str] = set()

    for i, row in enumerate(reader, start=1):
        narrative = (row.get("narrative") or "").strip()
        if not narrative:
            rows_out.append(UploadResultRow(row_number=i, status="FAILED", error="Missing required field: narrative"))
            failed += 1
            continue

        dedupe_key = narrative.lower()
        if dedupe_key in seen_narratives:
            rows_out.append(UploadResultRow(row_number=i, status="DUPLICATE", error="Duplicate narrative in this file"))
            duplicates += 1
            continue
        existing = db.query(Report).filter(Report.narrative == narrative).first()
        if existing:
            rows_out.append(UploadResultRow(row_number=i, status="DUPLICATE", error="Narrative already exists in database"))
            duplicates += 1
            continue
        seen_narratives.add(dedupe_key)

        occurred_at = None
        if row.get("occurred_at"):
            try:
                occurred_at = datetime.fromisoformat(row["occurred_at"].strip())
            except ValueError:
                pass

        try:
            payload = ReportCreate(
                report_type=(row.get("report_type") or "NEAR_MISS").strip().upper(),
                title=row.get("title") or "",
                narrative=narrative,
                site=row.get("site"),
                activity=row.get("activity"),
                location=row.get("location"),
                reporter_name=row.get("reporter_name"),
                occurred_at=occurred_at,
            )
            report = _create_report_row(db, payload, ReportSource.CSV_UPLOAD)
            db.commit()
            analyze_report(db, report)
            rows_out.append(UploadResultRow(row_number=i, status="SUCCESS", report_id=report.id))
            successful += 1
        except Exception as e:
            db.rollback()
            rows_out.append(UploadResultRow(row_number=i, status="FAILED", error=str(e)))
            failed += 1

    log_action(db, "REPORT", 0, "CSV_UPLOAD", user.email,
               {"filename": file.filename, "successful": successful, "failed": failed, "duplicates": duplicates})

    return UploadResult(
        total_rows=len(rows_out), successful=successful, failed=failed, duplicates=duplicates, rows=rows_out,
    )


@router.post("/{report_id}/analyze", response_model=ReportOut)
def reanalyze(report_id: int, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    report = db.query(Report).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    analysis = analyze_report(db, report)
    log_action(db, "REPORT", report.id, "REPORT_REANALYZED", user.email,
               {"sif_classification": analysis.sif_classification.value})
    return _serialize_report(report, analysis)


@router.get("", response_model=list[ReportListItem])
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    sif: str | None = None,
    site: str | None = None,
    activity: str | None = None,
    lsr: str | None = None,
    barrier: str | None = None,
    report_type: str | None = None,
    review_required: bool | None = None,
    search: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
):
    q = (
        db.query(Report, AnalysisResult)
        .outerjoin(AnalysisResult, AnalysisResult.report_id == Report.id)
        .options(joinedload(Report.site), joinedload(Report.activity))
        # PUBLIC_CORPUS rows are real historical incidents used only to ground
        # similarity search (see similarity_service.py) -- they are not OIL data
        # and are never listed as browsable reports.
        .filter(Report.source != ReportSource.PUBLIC_CORPUS)
    )
    if sif:
        q = q.filter(AnalysisResult.sif_classification == sif)
    if site:
        q = q.join(Site, Site.id == Report.site_id).filter(Site.name == site)
    if activity:
        q = q.join(Activity, Activity.id == Report.activity_id).filter(Activity.name == activity)
    if lsr:
        q = q.filter(AnalysisResult.primary_lsr == lsr)
    if barrier:
        q = q.join(
            ReportBarrier, ReportBarrier.analysis_id == AnalysisResult.id
        ).filter(ReportBarrier.barrier_type == barrier)
    if report_type:
        q = q.filter(Report.report_type == report_type)
    if review_required is not None:
        q = q.filter(AnalysisResult.review_required == review_required)
    if search:
        like = f"%{search}%"
        q = q.filter((Report.narrative.ilike(like)) | (Report.title.ilike(like)))
    if occurred_from:
        q = q.filter(Report.occurred_at >= occurred_from)
    if occurred_to:
        q = q.filter(Report.occurred_at <= occurred_to)

    q = q.order_by(Report.occurred_at.desc()).offset(offset).limit(limit).distinct()
    results = []
    for report, analysis in q.all():
        results.append(ReportListItem(
            id=report.id, report_code=report.report_code, report_type=report.report_type.value,
            title=report.title, site=report.site.name if report.site else None,
            activity=report.activity.name if report.activity else None,
            occurred_at=report.occurred_at,
            sif_classification=analysis.sif_classification.value if analysis else None,
            confidence=analysis.confidence if analysis else None,
            risk_score=analysis.risk_score if analysis else None,
            primary_lsr=analysis.primary_lsr if analysis else None,
            review_required=analysis.review_required if analysis else None,
        ))
    return results


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = db.query(Report).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    analysis = db.query(AnalysisResult).options(joinedload(AnalysisResult.barriers)).filter(
        AnalysisResult.report_id == report_id
    ).first()
    return _serialize_report(report, analysis)


@router.get("/{report_id}/fingerprint")
def get_fingerprint(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.analysis import PrecursorFingerprint
    fp = db.query(PrecursorFingerprint).filter(PrecursorFingerprint.report_id == report_id).first()
    if not fp:
        raise HTTPException(status_code=404, detail="Fingerprint not found. Analyze the report first.")
    return fp.fingerprint_json


@router.get("/{report_id}/similar", response_model=list[SimilarReportOut])
def get_similar(report_id: int, top_k: int = 5, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return find_similar_reports(db, report_id, top_k=top_k)


@router.get("/{report_id}/compare/{match_id}", response_model=PrecursorComparisonOut)
def get_comparison(
    report_id: int,
    match_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return compare_precursors(db, report_id, match_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{report_id}/explanation")
def get_explanation(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == report_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Analyze the report first.")
    return {
        "explanation": analysis.explanation_text,
        "explanation_source": analysis.explanation_source,
        "reason_codes": analysis.reason_codes,
        "sif_classification": analysis.sif_classification.value,
        "confidence": analysis.confidence,
    }
