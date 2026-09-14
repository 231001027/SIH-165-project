from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50))  # REPORT, ANALYSIS, REVIEW, USER
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True)
    component: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvaluationCase(Base):
    """Held-out gold-set labels, kept separate from production feedback so the
    evaluation harness never leaks into training (blueprint Part 3.3 / 5.3)."""

    __tablename__ = "evaluation_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, index=True)
    gold_sif: Mapped[str] = mapped_column(String(20))
    gold_lsr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gold_barrier_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    split: Mapped[str] = mapped_column(String(20), default="test")  # train | val | test
