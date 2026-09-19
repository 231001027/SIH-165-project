from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    report_type: str = Field(default="NEAR_MISS")
    title: str = ""
    narrative: str
    site: str | None = None
    activity: str | None = None
    location: str | None = None
    reporter_name: str | None = None
    occurred_at: datetime | None = None


class BarrierOut(BaseModel):
    barrier_type: str
    status: str
    evidence_text: str | None = None
    confidence: float

    class Config:
        from_attributes = True


class AnalysisOut(BaseModel):
    id: int
    model_version: str
    sif_classification: str
    confidence: float
    review_required: bool
    abstain_reason: str | None
    risk_score: float
    risk_breakdown: dict
    reason_codes: list
    primary_lsr: str | None
    primary_lsr_confidence: float | None
    secondary_lsr: str | None
    secondary_lsr_confidence: float | None
    lsr_evidence: list
    hazard: str | None
    energy_source: str | None
    energy_category: str | None
    exposure_description: str | None
    exposure_proximity: str | None
    activity_extracted: str | None
    location_extracted: str | None
    potential_consequence: str | None
    explanation_text: str
    explanation_source: str
    repeat_precursor_count: int
    original_prediction: dict | None = None
    oisd_classification: dict | None = None
    barriers: list[BarrierOut] = []

    class Config:
        from_attributes = True


class ReportOut(BaseModel):
    id: int
    report_code: str
    report_type: str
    title: str
    narrative: str
    site: str | None = None
    activity: str | None = None
    location: str | None = None
    source: str
    occurred_at: datetime
    created_at: datetime
    analysis: AnalysisOut | None = None

    class Config:
        from_attributes = True


class ReportListItem(BaseModel):
    id: int
    report_code: str
    report_type: str
    title: str
    site: str | None = None
    activity: str | None = None
    occurred_at: datetime
    sif_classification: str | None = None
    confidence: float | None = None
    risk_score: float | None = None
    primary_lsr: str | None = None
    review_required: bool | None = None


class UploadResultRow(BaseModel):
    row_number: int
    status: str  # SUCCESS | FAILED | DUPLICATE
    report_id: int | None = None
    error: str | None = None


class UploadResult(BaseModel):
    total_rows: int
    successful: int
    failed: int
    duplicates: int
    rows: list[UploadResultRow]


class SimilarReportOut(BaseModel):
    report_id: int
    report_code: str
    title: str
    similarity: float
    sif_potential: str | None
    life_saving_rule: str | None
    site: str | None
    activity: str | None
    occurred_at: str | None
    source: str = "INTERNAL"  # INTERNAL | PUBLIC_CORPUS
    citation_label: str | None = None
    citation_url: str | None = None
    excerpt: str | None = None
    narrative: str | None = None


class FieldComparisonOut(BaseModel):
    field: str
    shared: bool
    query_value: str | None = None
    match_value: str | None = None
    query_evidence: str | None = None
    match_evidence: str | None = None
    reason: str


class PrecursorComparisonOut(BaseModel):
    query_report_id: int
    match_report_id: int
    similarity: float | None = None
    query_narrative: str
    match_narrative: str
    match_title: str | None = None
    match_source: str | None = None
    citation_label: str | None = None
    citation_url: str | None = None
    query_highlights: list[str] = []
    match_highlights: list[str] = []
    fields: list[FieldComparisonOut] = []
