import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.playback import get_video_or_404
from app.config import get_settings
from app.db import get_db
from app.models.storage_tier import StorageTierEvent
from app.models.user import User
from app.models.video import StorageTier, VideoVersion
from app.schemas.archive import StorageTierEventOut
from app.security import get_current_user
from app.services import retention_service, storage_service
from app.services.audit_service import log_action

router = APIRouter(tags=["archive"])
settings = get_settings()


@router.post("/videos/{video_id}/archive", response_model=StorageTierEventOut)
def archive_video(
    video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StorageTierEvent:
    video = get_video_or_404(db, video_id)
    if video.storage_tier == StorageTier.COLD:
        raise HTTPException(status_code=400, detail="Video is already archived")

    retention_service.archive_video(db, video)
    event = (
        db.query(StorageTierEvent)
        .filter(StorageTierEvent.video_id == video.id)
        .order_by(StorageTierEvent.moved_at.desc())
        .first()
    )
    event.triggered_by = user.id
    db.commit()
    db.refresh(event)
    log_action(db, user, "archive.move_to_cold", "video", video.id, {})
    return event


@router.post("/videos/{video_id}/restore", response_model=StorageTierEventOut)
def restore_video(
    video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StorageTierEvent:
    """Restores archived evidence back to hot storage. The RFP allows up to
    24h for this in a real cold-storage tier (e.g. Glacier-class); this demo
    performs the copy immediately but still records the SLA-bound ETA for
    reporting so the workflow reads the same as production would."""
    video = get_video_or_404(db, video_id)
    if video.storage_tier != StorageTier.COLD:
        raise HTTPException(status_code=400, detail="Video is not archived")

    eta = datetime.utcnow() + timedelta(hours=settings.cold_storage_restore_sla_hours)
    for version in db.query(VideoVersion).filter(VideoVersion.video_id == video.id):
        if version.storage_tier == StorageTier.COLD:
            storage_service.move_between_tiers(StorageTier.COLD, StorageTier.HOT, version.storage_key)
            version.storage_tier = StorageTier.HOT
    video.storage_tier = StorageTier.HOT

    event = StorageTierEvent(video_id=video.id, tier=StorageTier.HOT, restore_eta=eta, triggered_by=user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    log_action(db, user, "archive.restore", "video", video.id, {"restore_eta": eta.isoformat()})
    return event


@router.get("/videos/{video_id}/storage-tier-events", response_model=list[StorageTierEventOut])
def list_tier_events(video_id: uuid.UUID, db: Session = Depends(get_db)) -> list[StorageTierEvent]:
    get_video_or_404(db, video_id)
    return (
        db.query(StorageTierEvent)
        .filter(StorageTierEvent.video_id == video_id)
        .order_by(StorageTierEvent.moved_at.desc())
        .all()
    )
