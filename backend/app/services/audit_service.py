from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(db: Session, entity_type: str, entity_id: int, action: str, actor: str, payload: dict | None = None) -> None:
    """Append-only audit trail entry. Never logs full narrative text -- only
    structured metadata -- per blueprint Part 7.2 'never log full narrative
    text in shared/dev logs'."""
    db.add(AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        payload=payload or {},
    ))
    db.commit()
