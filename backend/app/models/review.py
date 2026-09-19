import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# Hardcoded escalate strings that must be rejected (analyst must type a real reason).
FORBIDDEN_ESCALATE_REASONS = frozenset({
    "",
    "Escalated for senior HSE attention.",
    "Escalated by HSE analyst for further attention.",
})


class ReviewAction(str, enum.Enum):
    """HSE analyst review actions and their effects on AnalysisResult.

    APPROVE
        Analyst confirms the AI classification is correct as-is.
        Clears review_required; leaves classification unchanged.
        Logged as a positive validation signal for evaluation / retraining.

    MODIFY
        Analyst corrects one or more fields (AI was wrong on those fields).
        Clears review_required; updates AnalysisResult to the corrected values.
        original_prediction snapshot (JSON on AnalysisResult) is preserved —
        populated at analysis time and never overwritten on MODIFY — so the
        AI's original output is always recoverable (not only via Feedback diffs).

    REJECT
        Analyst determines this item should NOT be in the review queue at all
        (duplicate, spam, clearly out of scope). This is NOT "the AI was wrong,
        revert the classification" — use MODIFY for that.
        Clears review_required; leaves classification unchanged.

    ESCALATE
        Routes to senior HSE attention. review_required stays True.
        Requires a non-empty, non-default analyst-entered reason string.
    """

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
