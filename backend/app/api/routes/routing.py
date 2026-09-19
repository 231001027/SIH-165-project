"""Assignee routing config + response-time metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_analyst
from app.db.session import get_db
from app.models.notification import AssigneeRouting, AssigneeRole, NotificationLog
from app.models.user import User
from app.services.notification_service import response_time_metrics

router = APIRouter(tags=["routing"])


class RoutingOut(BaseModel):
    id: int
    site: str
    role: str
    person_name: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True


class RoutingUpdate(BaseModel):
    site: str | None = None
    role: str | None = None
    person_name: str | None = None
    email: str | None = None
    is_active: bool | None = None


class NotificationOut(BaseModel):
    id: int
    report_id: int
    assignee_id: int
    assignee_name: str | None = None
    assignee_email: str | None = None
    band_at_trigger: str
    sent_at: str | None = None
    acknowledged_at: str | None = None
    acknowledged_action: str | None = None


@router.get("/api/routing", response_model=list[RoutingOut])
def list_routing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(AssigneeRouting).order_by(AssigneeRouting.site, AssigneeRouting.role).all()
    return [
        RoutingOut(
            id=r.id, site=r.site, role=r.role.value if hasattr(r.role, "value") else r.role,
            person_name=r.person_name, email=r.email, is_active=r.is_active,
        )
        for r in rows
    ]


@router.put("/api/routing/{routing_id}", response_model=RoutingOut)
def update_routing(
    routing_id: int,
    payload: RoutingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    row = db.query(AssigneeRouting).filter(AssigneeRouting.id == routing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Routing row not found.")
    if payload.site is not None:
        row.site = payload.site
    if payload.role is not None:
        try:
            row.role = AssigneeRole(payload.role)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid role")
    if payload.person_name is not None:
        row.person_name = payload.person_name
    if payload.email is not None:
        row.email = payload.email
    if payload.is_active is not None:
        row.is_active = payload.is_active
    db.commit()
    db.refresh(row)
    return RoutingOut(
        id=row.id, site=row.site,
        role=row.role.value if hasattr(row.role, "value") else row.role,
        person_name=row.person_name, email=row.email, is_active=row.is_active,
    )


@router.get("/api/reports/{report_id}/notifications", response_model=list[NotificationOut])
def report_notifications(
    report_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
):
    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.report_id == report_id)
        .order_by(NotificationLog.sent_at.desc())
        .all()
    )
    out = []
    for n in rows:
        assignee = db.query(AssigneeRouting).filter(AssigneeRouting.id == n.assignee_id).first()
        out.append(NotificationOut(
            id=n.id,
            report_id=n.report_id,
            assignee_id=n.assignee_id,
            assignee_name=assignee.person_name if assignee else None,
            assignee_email=assignee.email if assignee else None,
            band_at_trigger=n.band_at_trigger,
            sent_at=n.sent_at.isoformat() if n.sent_at else None,
            acknowledged_at=n.acknowledged_at.isoformat() if n.acknowledged_at else None,
            acknowledged_action=n.acknowledged_action,
        ))
    return out


@router.get("/api/metrics/response-time")
def metrics_response_time(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return response_time_metrics(db)
