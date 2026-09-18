import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.case import Case
from app.models.folder import Folder
from app.models.redaction import RedactionJob
from app.models.user import User
from app.models.video import StorageTier, Video, VideoVersion, VideoVersionKind
from app.schemas.redaction import (
    AutoTrackRequest,
    DetectFacesRequest,
    RedactionJobCreate,
    RedactionJobOut,
)
from app.security import get_current_user
from app.services import redaction_service, storage_service, watermark_service
from app.services.audit_service import log_action

router = APIRouter(tags=["redaction"])


def _get_video(db: Session, video_id: uuid.UUID) -> Video:
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def _get_version(db: Session, version_id: uuid.UUID) -> VideoVersion:
    version = db.get(VideoVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Video version not found")
    return version


def _download_version(version: VideoVersion, dest_dir: Path) -> Path:
    ext = Path(version.storage_key).suffix or ".mp4"
    local_path = dest_dir / f"source{ext}"
    storage_service.download_to_path(version.storage_tier, version.storage_key, str(local_path))
    return local_path


@router.post("/videos/{video_id}/detect-faces")
def detect_faces(
    video_id: uuid.UUID,
    payload: DetectFacesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Runs face detection on sampled frames of a version, returning raw
    detections the redaction UI offers as one-click auto-tracking starting
    points."""
    _get_video(db, video_id)
    version = _get_version(db, payload.version_id)
    with tempfile.TemporaryDirectory() as tmp:
        local_path = _download_version(version, Path(tmp))
        detections = redaction_service.detect_faces_in_video(local_path, payload.sample_every_seconds)
    log_action(
        db, user, "redaction.detect_faces", "video", video_id, {"count": len(detections)}
    )
    return detections


@router.post("/videos/{video_id}/auto-track")
def auto_track(
    video_id: uuid.UUID,
    payload: AutoTrackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """"Select individual -> system follows person": runs a visual tracker
    forward from a single clicked box, returning a track ready to attach to
    a redaction job."""
    _get_video(db, video_id)
    version = _get_version(db, payload.version_id)
    with tempfile.TemporaryDirectory() as tmp:
        local_path = _download_version(version, Path(tmp))
        try:
            frames = redaction_service.auto_track(
                local_path, payload.start_t, payload.x, payload.y, payload.w, payload.h, payload.max_seconds
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    track = {"track_id": str(uuid.uuid4()), "label": payload.label, "frames": frames}
    log_action(
        db, user, "redaction.auto_track", "video", video_id,
        {"track_id": track["track_id"], "frame_count": len(frames)},
    )
    return track


@router.post(
    "/videos/{video_id}/redaction-jobs",
    response_model=RedactionJobOut,
    status_code=status.HTTP_201_CREATED,
)
def create_redaction_job(
    video_id: uuid.UUID,
    payload: RedactionJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RedactionJob:
    """Creates and synchronously renders a redaction job: blurs the given
    region tracks (if any) and mutes the given audio segments (if any),
    producing a new immutable VideoVersion. The source version and original
    are never modified — this is what makes "reopen previous versions /
    correct previous redactions" possible: just create another job against
    the same or an earlier source version."""
    video = _get_video(db, video_id)
    source_version = _get_version(db, payload.source_version_id)
    if source_version.video_id != video.id:
        raise HTTPException(status_code=400, detail="source_version_id does not belong to this video")

    job = RedactionJob(
        video_id=video.id,
        source_version_id=source_version.id,
        type=payload.type,
        regions=[r.model_dump() for r in payload.regions],
        audio_segments=[s.model_dump() for s in payload.audio_segments],
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        redaction_service.run_redaction_job(db, job, video, source_version)
    except redaction_service.RedactionRenderError as exc:
        raise HTTPException(status_code=500, detail=f"Redaction render failed: {exc}") from exc
    db.refresh(job)

    log_action(
        db, user, "redaction.job.create", "video", video.id,
        {"job_id": str(job.id), "type": job.type.value, "result_version_id": str(job.result_version_id)},
    )
    return job


@router.get("/videos/{video_id}/redaction-jobs", response_model=list[RedactionJobOut])
def list_redaction_jobs(video_id: uuid.UUID, db: Session = Depends(get_db)) -> list[RedactionJob]:
    return (
        db.query(RedactionJob)
        .filter(RedactionJob.video_id == video_id)
        .order_by(RedactionJob.created_at.desc())
        .all()
    )


@router.get("/redaction-jobs/{job_id}", response_model=RedactionJobOut)
def get_redaction_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> RedactionJob:
    job = db.get(RedactionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Redaction job not found")
    return job


@router.post(
    "/videos/{video_id}/versions/{version_id}/publish-disclosure",
    status_code=status.HTTP_201_CREATED,
)
def publish_disclosure_copy(
    video_id: uuid.UUID,
    version_id: uuid.UUID,
    apply_watermark: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Republishes a redacted version as a disclosure copy — the artifact
    that ultimately gets shared externally, kept as its own immutable
    version so the redacted "working copy" and the disclosure copy stay
    distinguishable in the version history. Burns in the publisher's
    effective watermark (user override, else the admin-configured global
    one) unless `apply_watermark=false` or none is configured/enabled."""
    video = _get_video(db, video_id)
    source_version = _get_version(db, version_id)
    if source_version.video_id != video.id:
        raise HTTPException(status_code=400, detail="Version does not belong to this video")

    dest_key = f"videos/{video.id}/disclosure/{uuid.uuid4()}.mp4"
    watermarked = False

    watermark = watermark_service.get_effective_watermark(db, user) if apply_watermark else None
    if watermark and watermark.enabled_for_export:
        folder = db.get(Folder, video.folder_id)
        case = db.get(Case, folder.case_id) if folder else None
        text = watermark_service.render_template(
            watermark.template,
            viewer_name=user.name,
            viewer_email=user.email,
            case_name=case.name if case else "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_local = _download_version(source_version, tmp_path)
            output_local = tmp_path / "disclosure.mp4"
            watermark_service.burn_in_watermark(source_local, output_local, text)
            storage_service.put_file(StorageTier.HOT, dest_key, str(output_local))
        watermarked = True
    else:
        storage_service.copy_object(source_version.storage_tier, source_version.storage_key, dest_key)

    disclosure = VideoVersion(
        video_id=video.id,
        parent_version_id=source_version.id,
        kind=VideoVersionKind.DISCLOSURE,
        storage_key=dest_key,
        storage_tier=StorageTier.HOT if watermarked else source_version.storage_tier,
        watermark_applied=watermarked,
        created_by=user.id,
        notes="Disclosure copy published for sharing.",
    )
    db.add(disclosure)
    db.commit()
    db.refresh(disclosure)

    log_action(
        db, user, "redaction.publish_disclosure", "video", video.id,
        {"source_version_id": str(version_id), "disclosure_version_id": str(disclosure.id)},
    )
    return {"id": str(disclosure.id), "storage_key": dest_key}
