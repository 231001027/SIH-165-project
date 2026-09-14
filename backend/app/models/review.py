import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ReviewAction(str, enum.Enum):
    APPROVE = "APPROVE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ReviewAction] = mapped_column(Enum(ReviewAction))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    reviewer: Mapped["User"] = relationship("User")


class Feedback(Base):
    """One row per corrected field, derived from a MODIFY review action.
    Kept separate from HumanReview so future model retraining can query
    corrections field-by-field (blueprint Part 1.3 Stage 18 / Part 6.5)."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("human_reviews.id"))
    field_name: Mapped[str] = mapped_column(String(100))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
