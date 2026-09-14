from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit_logs(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    limit: int = Query(default=200, le=1000),
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "action": r.action, "actor": r.actor, "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
