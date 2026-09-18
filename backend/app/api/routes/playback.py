import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.video import Video, VideoVersion, VideoVersionKind
from app.models.user import User
from app.schemas.video import VideoOut, VideoVersionOut
from app.security import get_current_user
from app.services.playback_service import build_stream_response

router = APIRouter(prefix="/videos", tags=["playback"])


def get_video_or_404(db: Session, video_id: uuid.UUID) -> Video:
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def latest_version_or_404(db: Session, video_id: uuid.UUID, kind: VideoVersionKind | None = None) -> VideoVersion:
    query = db.query(VideoVersion).filter(VideoVersion.video_id == video_id)
    if kind:
        query = query.filter(VideoVersion.kind == kind)
    version = query.order_by(VideoVersion.created_at.desc()).first()
    if not version:
        raise HTTPException(status_code=404, detail="No version available for this video")
    return version


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)) -> Video:
    return get_video_or_404(db, video_id)


@router.get("/{video_id}/versions", response_model=list[VideoVersionOut])
def list_versions(video_id: uuid.UUID, db: Session = Depends(get_db)) -> list[VideoVersion]:
    get_video_or_404(db, video_id)
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
    video = get_video_or_404(db, video_id)
    version = (
        db.get(VideoVersion, version_id) if version_id else latest_version_or_404(db, video_id)
    )
    if not version or version.video_id != video.id:
        raise HTTPException(status_code=404, detail="Version not found for this video")

    return build_stream_response(request, db, video, version, user)
