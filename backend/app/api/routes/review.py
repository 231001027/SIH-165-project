from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_analyst, require_admin
from app.db.session import get_db
from app.models.analysis import AnalysisResult, SifClassification
from app.models.report import Report
from app.models.review import HumanReview, ReviewAction, Feedback
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewOut, ReviewQueueItem
from app.services.audit_service import log_action
from app.services.retrain_service import retrain_classifier_from_feedback

router = APIRouter(prefix="/api/review", tags=["review"])

EDITABLE_FIELDS = {
    "sif_classification", "primary_lsr", "hazard", "energy_source",
    "exposure_description", "exposure_proximity", "activity_extracted",
    "location_extracted", "potential_consequence",
}


@router.post("/retrain")
def retrain_from_feedback(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """Retrain SIF classifier using gold/analysis labels + Feedback corrections."""
    result = retrain_classifier_from_feedback(db)
    log_action(
        db,
        entity_type="model",
        entity_id=0,
        action="RETRAIN_CLASSIFIER",
        actor=user.email,
        payload=result,
    )
    return result



@router.get("", response_model=list[ReviewQueueItem])
def review_queue(db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    rows = (
        db.query(Report, AnalysisResult)
        .join(AnalysisResult, AnalysisResult.report_id == Report.id)
        .options(joinedload(Report.site), joinedload(Report.activity))
        .filter(AnalysisResult.review_required == True)  # noqa: E712
        .order_by(Report.occurred_at.desc())
        .all()
    )
    return [
        ReviewQueueItem(
            report_id=report.id, report_code=report.report_code, title=report.title,
            narrative=report.narrative, sif_classification=analysis.sif_classification.value,
            confidence=analysis.confidence, review_required=analysis.review_required,
            abstain_reason=analysis.abstain_reason, primary_lsr=analysis.primary_lsr,
            hazard=analysis.hazard, energy_source=analysis.energy_source,
            exposure_description=analysis.exposure_description,
            exposure_proximity=analysis.exposure_proximity,
            activity_extracted=analysis.activity_extracted,
            location_extracted=analysis.location_extracted,
            potential_consequence=analysis.potential_consequence,
            site=report.site.name if report.site else None,
            activity=report.activity.name if report.activity else None,
            occurred_at=report.occurred_at,
        )
        for report, analysis in rows
    ]


@router.post("/{report_id}", response_model=ReviewOut)
def submit_review(report_id: int, payload: ReviewCreate, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    analysis = db.query(AnalysisResult).filter(AnalysisResult.report_id == report_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this report.")

    try:
        action = ReviewAction(payload.action)
    except ValueError:
        raise HTTPException(status_code=422, detail="action must be one of APPROVE, MODIFY, REJECT, ESCALATE")

    corrected_fields = {}
    if action == ReviewAction.MODIFY:
        if not analysis.original_prediction:
            analysis.original_prediction = {
                "sif_classification": analysis.sif_classification.value if hasattr(analysis.sif_classification, "value") else str(analysis.sif_classification),
                "confidence": analysis.confidence,
                "primary_lsr": analysis.primary_lsr,
                "hazard": analysis.hazard,
                "energy_source": analysis.energy_source,
                "exposure_description": analysis.exposure_description,
                "exposure_proximity": analysis.exposure_proximity,
                "activity_extracted": analysis.activity_extracted,
                "location_extracted": analysis.location_extracted,
                "potential_consequence": analysis.potential_consequence,
                "risk_score": analysis.risk_score,
                "reason_codes": analysis.reason_codes,
            }
        for field, new_value in (payload.corrected_fields or {}).items():
            if field not in EDITABLE_FIELDS:
                continue
            old_value = getattr(analysis, field)
            old_value_str = old_value.value if hasattr(old_value, "value") else old_value
            if str(old_value_str) == str(new_value):
                continue
            if field == "sif_classification":
                try:
                    setattr(analysis, field, SifClassification(new_value))
                except ValueError:
                    raise HTTPException(status_code=422, detail=f"Invalid sif_classification value: {new_value}")
            else:
                setattr(analysis, field, new_value)
            corrected_fields[field] = {"old": old_value_str, "new": new_value}
        analysis.review_required = False

    elif action == ReviewAction.APPROVE:
        analysis.review_required = False

    elif action == ReviewAction.REJECT:
        analysis.review_required = False

    elif action == ReviewAction.ESCALATE:
        analysis.review_required = True
        prefix = "ESCALATED"
        analysis.abstain_reason = f"{prefix}: {payload.reason or 'Escalated by HSE analyst for further attention.'}"

    review = HumanReview(
        report_id=report_id, reviewer_id=user.id, action=action,
        reason=payload.reason, corrected_fields=corrected_fields,
    )
    db.add(review)
    db.flush()

    for field, change in corrected_fields.items():
        db.add(Feedback(
            report_id=report_id, review_id=review.id, field_name=field,
            old_value=str(change["old"]), new_value=str(change["new"]), reviewer_id=user.id,
        ))

    db.commit()
    db.refresh(review)

    log_action(db, "REVIEW", review.id, f"REVIEW_{action.value}", user.email,
               {"report_id": report_id, "corrected_field_count": len(corrected_fields)})

    return ReviewOut.model_validate(review)
