import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.video import Video, VideoVersion, VideoVersionKind
from app.models.user import User
from app.schemas.video import VideoOut, VideoVersionOut
from app.security import get_current_user
from app.services import storage_service, video_pipeline
from app.services.audit_service import log_action

router = APIRouter(prefix="/videos", tags=["playback"])


def _get_video(db: Session, video_id: uuid.UUID) -> Video:
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def _latest_version(db: Session, video_id: uuid.UUID, kind: VideoVersionKind | None = None) -> VideoVersion:
    query = db.query(VideoVersion).filter(VideoVersion.video_id == video_id)
    if kind:
        query = query.filter(VideoVersion.kind == kind)
    version = query.order_by(VideoVersion.created_at.desc()).first()
    if not version:
        raise HTTPException(status_code=404, detail="No version available for this video")
    return version


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)) -> Video:
    return _get_video(db, video_id)


@router.get("/{video_id}/versions", response_model=list[VideoVersionOut])
def list_versions(video_id: uuid.UUID, db: Session = Depends(get_db)) -> list[VideoVersion]:
    _get_video(db, video_id)
    return (
        db.query(VideoVersion)
        .filter(VideoVersion.video_id == video_id)
        .order_by(VideoVersion.created_at.desc())
        .all()
    )


@router.get("/{video_id}/stream")
def stream_video(
    video_id: uuid.UUID,
    request: Request,
    version_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Streams a playable MP4 for the given (or latest) version with HTTP
    Range support, so the frontend <video> player can seek without
    downloading the whole file — this is what lets staff "view videos
    directly within DEMS ... without exporting to external tools"."""
    video = _get_video(db, video_id)
    version = (
        db.get(VideoVersion, version_id) if version_id else _latest_version(db, video_id)
    )
    if not version or version.video_id != video.id:
        raise HTTPException(status_code=404, detail="Version not found for this video")

    try:
        playable_key = video_pipeline.ensure_playable_mp4(
            str(video.id), version.storage_key, video.format
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot play this video: {exc}",
        ) from exc

    head = storage_service.head_object(version.storage_tier, playable_key)
    total_size = head["ContentLength"]

    range_header = request.headers.get("range")
    if range_header:
        _, _, range_spec = range_header.partition("=")
        start_str, _, end_str = range_spec.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else total_size - 1
        s3_range = f"bytes={start}-{end}"
        obj = storage_service.get_object_stream(version.storage_tier, playable_key, s3_range)
        chunk_len = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_len),
        }
        log_action(db, user, "video.view", "video", video.id, {"version_id": str(version.id)})
        return StreamingResponse(
            obj["Body"].iter_chunks(), status_code=206, media_type="video/mp4", headers=headers
        )

    obj = storage_service.get_object_stream(version.storage_tier, playable_key)
    log_action(db, user, "video.view", "video", video.id, {"version_id": str(version.id)})
    return StreamingResponse(
        obj["Body"].iter_chunks(),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(total_size)},
    )
