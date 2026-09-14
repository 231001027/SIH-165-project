from datetime import datetime

from pydantic import BaseModel


class ReviewCreate(BaseModel):
    action: str  # APPROVE | MODIFY | REJECT | ESCALATE
    reason: str | None = None
    corrected_fields: dict = {}


class ReviewOut(BaseModel):
    id: int
    report_id: int
    reviewer_id: int
    action: str
    reason: str | None
    corrected_fields: dict
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewQueueItem(BaseModel):
    report_id: int
    report_code: str
    title: str
    narrative: str
    sif_classification: str
    confidence: float
    review_required: bool
    abstain_reason: str | None
    primary_lsr: str | None
    site: str | None
    activity: str | None
    occurred_at: datetime
