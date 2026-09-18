import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def log_action(
    db: Session,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    details: dict | None = None,
) -> AuditLog:
    """Writes one append-only chain-of-custody / audit trail entry. Called
    from every mutating route (ingestion, playback view, redaction, sharing,
    retention change, deletion) so the full evidence history is
    reconstructable and exportable later via /audit routes."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_label=actor.email if actor else "system",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
