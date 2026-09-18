import csv
import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


def _filtered_query(
    db: Session,
    resource_type: str | None,
    resource_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str | None,
):
    query = db.query(AuditLog)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.asc())


@router.get("/logs", response_model=list[AuditLogOut])
def list_audit_logs(
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    return _filtered_query(db, resource_type, resource_id, actor_id, action).limit(limit).all()


@router.get("/videos/{video_id}/chain-of-custody", response_model=list[AuditLogOut])
def chain_of_custody(video_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AuditLog]:
    """Every recorded interaction with a piece of video evidence — upload,
    retrieval, viewing, redaction, sharing, download, retention changes,
    deletion — in chronological order, exportable as evidence of custody."""
    return _filtered_query(db, "video", video_id, None, None).all()


@router.get("/export")
def export_audit_csv(
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    logs = _filtered_query(db, resource_type, resource_id, None, None).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "actor", "action", "resource_type", "resource_id", "details"])
    for log in logs:
        writer.writerow(
            [
                log.timestamp.isoformat(),
                log.actor_label or "",
                log.action,
                log.resource_type,
                str(log.resource_id) if log.resource_id else "",
                log.details,
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )
