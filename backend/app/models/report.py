import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ReportType(str, enum.Enum):
    UNSAFE_ACT = "UNSAFE_ACT"
    UNSAFE_CONDITION = "UNSAFE_CONDITION"
    NEAR_MISS = "NEAR_MISS"
    INCIDENT = "INCIDENT"


class ReportSource(str, enum.Enum):
    MANUAL = "MANUAL"
    CSV_UPLOAD = "CSV_UPLOAD"
    SYNTHETIC_SEED = "SYNTHETIC_SEED"
    # A small, real, publicly-cited reference corpus (e.g. OSHA fatality/severe-injury
    # investigation summaries) used ONLY to ground similar-precursor retrieval against
    # genuine historical incidents -- never OIL data, never counted in KPIs/trends/
    # rankings/evaluation (see services/similarity_service.py and the exclusion filters
    # in trend_service.py / ranking_service.py / api/routes/dashboard.py).
    PUBLIC_CORPUS = "PUBLIC_CORPUS"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), default=ReportType.NEAR_MISS)
    title: Mapped[str] = mapped_column(String(500), default="")
    narrative: Mapped[str] = mapped_column(Text)

    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reporter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[ReportSource] = mapped_column(Enum(ReportSource), default=ReportSource.MANUAL)

    # Populated only for source=PUBLIC_CORPUS: a real, verifiable citation for a
    # genuine historical incident (see data/reference_corpus/incidents.json), so the
    # UI can show "grounded against a real documented incident" with a working link
    # rather than an internal report-detail page.
    citation_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Provenance for PUBLIC_CORPUS rows: REAL_OSHA | REAL_DGMS | SYNTHETIC_DEMO
    provenance: Mapped[str | None] = mapped_column(String(40), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    site: Mapped["Site"] = relationship("Site")
    activity: Mapped["Activity"] = relationship("Activity")
