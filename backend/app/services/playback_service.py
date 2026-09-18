from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.video import Video, VideoVersion
from app.services import storage_service, video_pipeline
from app.services.audit_service import log_action


def build_stream_response(
    request: Request,
    db: Session,
    video: Video,
    version: VideoVersion,
    actor: User | None,
    audit_action: str = "video.view",
    audit_details: dict | None = None,
) -> StreamingResponse:
    """Shared byte-range streaming logic used by both the authenticated
    playback endpoint and the public share-link endpoint, so external
    recipients (police/insurance/court/FOI/guest) get the same seekable
    playback experience as internal staff."""
    try:
        playable_key = video_pipeline.ensure_playable_mp4(
            str(video.id), version.storage_key, video.format
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot play this video: {exc}",
        ) from exc

    try:
        head = storage_service.head_object(version.storage_tier, playable_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video content not found in storage (it may have been deleted).",
        ) from exc
    total_size = head["ContentLength"]
    details = {"version_id": str(version.id), **(audit_details or {})}

    range_header = request.headers.get("range")
    if range_header:
        _, _, range_spec = range_header.partition("=")
        start_str, _, end_str = range_spec.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else total_size - 1
        s3_range = f"bytes={start}-{end}"
        obj = storage_service.get_object_stream(version.storage_tier, playable_key, s3_range)
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        log_action(db, actor, audit_action, "video", video.id, details)
        return StreamingResponse(
            obj["Body"].iter_chunks(), status_code=206, media_type="video/mp4", headers=headers
        )

    obj = storage_service.get_object_stream(version.storage_tier, playable_key)
    log_action(db, actor, audit_action, "video", video.id, details)
    return StreamingResponse(
        obj["Body"].iter_chunks(),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(total_size)},
    )
