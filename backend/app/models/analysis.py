import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, Float, JSON, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SifClassification(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NON_SIF = "NON_SIF"
    REVIEW = "REVIEW"
    # Distinct from REVIEW: narrative failed the English-only rule-pipeline gate.
    # Not a SIF risk band — automated analysis was not run.
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"


class BarrierStatus(str, enum.Enum):
    PRESENT_EFFECTIVE = "PRESENT_EFFECTIVE"
    MISSING = "MISSING"
    FAILED = "FAILED"
    BYPASSED = "BYPASSED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNKNOWN = "UNKNOWN"


class AnalysisResult(Base):
    """The core AI output for one report (one current row per report; re-analysis overwrites in place
    for the hackathon MVP, with model_version recorded so results stay attributable)."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(50), default="sifguard-v0.1-prototype")

    sif_classification: Mapped[SifClassification] = mapped_column(Enum(SifClassification))
    confidence: Mapped[float] = mapped_column(Float)  # 0-100
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    abstain_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    risk_score: Mapped[float] = mapped_column(Float)  # 0-100
    risk_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)

    primary_lsr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_lsr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    secondary_lsr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_lsr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    lsr_evidence: Mapped[list] = mapped_column(JSON, default=list)

    hazard: Mapped[str | None] = mapped_column(String(255), nullable=True)
    energy_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    energy_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exposure_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exposure_proximity: Mapped[str | None] = mapped_column(String(50), nullable=True)  # HIGH/MEDIUM/LOW/NONE

    activity_extracted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_extracted: Mapped[str | None] = mapped_column(String(255), nullable=True)

    potential_consequence: Mapped[str | None] = mapped_column(String(500), nullable=True)
    explanation_text: Mapped[str] = mapped_column(Text, default="")
    explanation_source: Mapped[str] = mapped_column(String(30), default="template")  # template | llm_enhanced

    # Snapshot of the model output before any HumanReview MODIFY mutation.
    original_prediction: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # OISD-style consequence-probability lens (alongside sif_classification — does not replace it).
    oisd_classification: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    repeat_precursor_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    report: Mapped["Report"] = relationship("Report")
    entities: Mapped[list["ReportEntity"]] = relationship(
        "ReportEntity", back_populates="analysis", cascade="all, delete-orphan"
    )
    barriers: Mapped[list["ReportBarrier"]] = relationship(
        "ReportBarrier", back_populates="analysis", cascade="all, delete-orphan"
    )


class ReportEntity(Base):
    __tablename__ = "report_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"))
    entity_type: Mapped[str] = mapped_column(String(50))  # HAZARD, ENERGY, EXPOSURE, ACTIVITY, LOCATION, EQUIPMENT
    entity_text: Mapped[str] = mapped_column(String(500))
    evidence_span: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    analysis: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="entities")


class ReportBarrier(Base):
    __tablename__ = "report_barriers"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"))
    barrier_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[BarrierStatus] = mapped_column(Enum(BarrierStatus))
    evidence_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    analysis: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="barriers")


class PrecursorFingerprint(Base):
    """The reusable 'unit of intelligence' (blueprint Part 3.6): one structured summary per report,
    plus its embedding vector, used by similarity search / clustering / trends / ranking."""

    __tablename__ = "precursor_fingerprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), unique=True, index=True)
    fingerprint_json: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[list] = mapped_column(JSON)  # dense vector, stored as JSON list of floats
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("precursor_clusters.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PrecursorCluster(Base):
    __tablename__ = "precursor_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(50), default="kmeans")
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    top_terms: Mapped[list] = mapped_column(JSON, default=list)
    dominant_lsr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dominant_site: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
