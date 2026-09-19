"""Hi-Po / HIGH push-notification routing and acknowledgment audit trail."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AssigneeRole(str, enum.Enum):
    SITE_HSE_OFFICER = "SITE_HSE_OFFICER"
    SITE_HSE_MANAGER = "SITE_HSE_MANAGER"
    UNIT_HEAD = "UNIT_HEAD"


class AssigneeRouting(Base):
    """Demo site→person routing config (not real OIL contacts)."""

    __tablename__ = "assignee_routing"

    id: Mapped[int] = mapped_column(primary_key=True)
    site: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[AssigneeRole] = mapped_column(Enum(AssigneeRole))
    person_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("assignee_routing.id"), index=True)
    band_at_trigger: Mapped[str] = mapped_column(String(50))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_action: Mapped[str | None] = mapped_column(String(30), nullable=True)

    assignee: Mapped["AssigneeRouting"] = relationship("AssigneeRouting")
