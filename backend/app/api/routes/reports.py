from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit import AuditLog
from app.models.case import Case
from app.models.folder import Folder
from app.models.redaction import RedactionJob
from app.models.video import Video, VideoStatus

router = APIRouter(prefix="/reports", tags=["reports"])

# These endpoints return plain JSON aggregates. They're the integration
# point for Power BI (via its Web/JSON connector, or by pointing Power BI
# directly at the Postgres database for richer modeling) and back the
# frontend's ReportsDashboard.


@router.get("/inventory")
def video_inventory(db: Session = Depends(get_db)) -> dict:
    by_status = dict(db.query(Video.status, func.count(Video.id)).group_by(Video.status).all())
    by_format = dict(db.query(Video.format, func.count(Video.id)).group_by(Video.format).all())
    total_count, total_size = db.query(func.count(Video.id), func.coalesce(func.sum(Video.size_bytes), 0)).one()
    return {
        "total_videos": total_count,
        "total_size_bytes": int(total_size),
        "by_status": {k.value: v for k, v in by_status.items()},
        "by_format": by_format,
    }


@router.get("/storage-utilization")
def storage_utilization(db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(Video.storage_tier, func.count(Video.id), func.coalesce(func.sum(Video.size_bytes), 0))
        .filter(Video.status != VideoStatus.DELETED)
        .group_by(Video.storage_tier)
        .all()
    )
    return {
        tier.value: {"count": count, "size_bytes": int(size)}
        for tier, count, size in rows
    }


@router.get("/redaction-workload")
def redaction_workload(db: Session = Depends(get_db)) -> dict:
    by_type = dict(db.query(RedactionJob.type, func.count(RedactionJob.id)).group_by(RedactionJob.type).all())
    by_status = dict(
        db.query(RedactionJob.status, func.count(RedactionJob.id)).group_by(RedactionJob.status).all()
    )
    by_user = db.query(RedactionJob.created_by, func.count(RedactionJob.id)).group_by(RedactionJob.created_by).all()
    return {
        "by_type": {k.value: v for k, v in by_type.items()},
        "by_status": {k.value: v for k, v in by_status.items()},
        "by_user": {str(u): c for u, c in by_user if u},
    }


@router.get("/user-activity")
def user_activity(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(AuditLog.actor_label, AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.actor_label, AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(500)
        .all()
    )
    return [{"actor": actor, "action": action, "count": count} for actor, action, count in rows]


@router.get("/evidence-access")
def evidence_access(db: Session = Depends(get_db)) -> list[dict]:
    access_actions = ["video.view", "share.view", "share.download", "video.download"]
    rows = (
        db.query(AuditLog.resource_id, func.count(AuditLog.id))
        .filter(AuditLog.resource_type == "video", AuditLog.action.in_(access_actions))
        .group_by(AuditLog.resource_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(100)
        .all()
    )
    return [{"video_id": str(video_id), "access_count": count} for video_id, count in rows if video_id]


@router.get("/investigation-workload")
def investigation_workload(db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Case.id, Case.name, func.count(Video.id))
        .join(Folder, Folder.case_id == Case.id)
        .join(Video, Video.folder_id == Folder.id)
        .group_by(Case.id, Case.name)
        .order_by(func.count(Video.id).desc())
        .all()
    )
    return [{"case_id": str(cid), "case_name": name, "video_count": count} for cid, name, count in rows]
