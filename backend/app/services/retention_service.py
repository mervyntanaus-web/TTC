from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.retention import RetentionPolicy
from app.models.video import StorageTier, Video, VideoStatus
from app.models.storage_tier import StorageTierEvent
from app.services import storage_service

DEFAULT_POLICY = RetentionPolicy(
    category="standard", retention_days=365, auto_delete=False, auto_archive_after_days=None
)


def get_policy(db: Session, category: str) -> RetentionPolicy:
    return db.query(RetentionPolicy).filter(RetentionPolicy.category == category).first() or DEFAULT_POLICY


def compute_expiry(video: Video, policy: RetentionPolicy) -> datetime:
    return video.uploaded_at + timedelta(days=policy.retention_days)


def compute_archive_at(video: Video, policy: RetentionPolicy) -> datetime | None:
    if not policy.auto_archive_after_days:
        return None
    return video.uploaded_at + timedelta(days=policy.auto_archive_after_days)


@dataclass
class RetentionStatus:
    category: str
    expires_at: datetime
    archive_at: datetime | None
    legal_hold: bool
    eligible_for_deletion: bool
    eligible_for_archive: bool


def retention_status(db: Session, video: Video, now: datetime | None = None) -> RetentionStatus:
    now = now or datetime.utcnow()
    policy = get_policy(db, video.retention_category)
    expires_at = compute_expiry(video, policy)
    archive_at = compute_archive_at(video, policy)
    return RetentionStatus(
        category=policy.category,
        expires_at=expires_at,
        archive_at=archive_at,
        legal_hold=video.legal_hold,
        eligible_for_deletion=(
            not video.legal_hold and policy.auto_delete and now >= expires_at and video.status != VideoStatus.DELETED
        ),
        eligible_for_archive=(
            not video.legal_hold
            and archive_at is not None
            and now >= archive_at
            and video.storage_tier == StorageTier.HOT
            and video.status != VideoStatus.DELETED
        ),
    )


@dataclass
class SweepResult:
    archived: list = field(default_factory=list)
    deleted: list = field(default_factory=list)


def archive_video(db: Session, video: Video) -> None:
    from app.models.video import VideoVersion  # avoid circular import at module load

    for version in db.query(VideoVersion).filter(VideoVersion.video_id == video.id):
        if version.storage_tier == StorageTier.HOT:
            storage_service.move_between_tiers(StorageTier.HOT, StorageTier.COLD, version.storage_key)
            version.storage_tier = StorageTier.COLD
    video.storage_tier = StorageTier.COLD
    db.add(StorageTierEvent(video_id=video.id, tier=StorageTier.COLD))
    db.commit()


def delete_video(db: Session, video: Video) -> None:
    """Soft-deletes: removes the underlying storage objects but preserves
    the Video catalog row (and its metadata) as a tombstone, per "automatic
    deletion" + "preservation of metadata after deletion"."""
    from app.models.video import VideoVersion  # avoid circular import at module load

    for version in db.query(VideoVersion).filter(VideoVersion.video_id == video.id):
        storage_service.delete_object(version.storage_tier, version.storage_key)
    video.status = VideoStatus.DELETED
    video.deleted_at = datetime.utcnow()
    db.commit()


def run_sweep(db: Session, now: datetime | None = None) -> SweepResult:
    """Applies retention policy to every non-deleted video: archives videos
    past their auto-archive threshold to cold storage, and deletes videos
    past their retention period where the policy allows auto-delete —
    always respecting legal holds. Intended to run on a schedule (see
    app/worker/jobs.py); also exposed as a manual admin trigger for demos."""
    now = now or datetime.utcnow()
    result = SweepResult()
    for video in db.query(Video).filter(Video.status != VideoStatus.DELETED):
        status = retention_status(db, video, now)
        if status.eligible_for_archive:
            archive_video(db, video)
            result.archived.append(video.id)
        if status.eligible_for_deletion:
            delete_video(db, video)
            result.deleted.append(video.id)
    return result
