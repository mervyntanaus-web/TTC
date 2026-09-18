import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, String, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.folder import Folder
from app.models.transcript import Transcript
from app.models.video import Video
from app.schemas.video import VideoOut

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/videos", response_model=list[VideoOut])
def search_videos(
    q: str | None = Query(None, description="Keyword search across filename/metadata/transcript"),
    case_id: uuid.UUID | None = None,
    folder_id: uuid.UUID | None = None,
    metadata_field: str | None = Query(None, description="Dot-free JSON key to filter on"),
    metadata_value: str | None = None,
    db: Session = Depends(get_db),
) -> list[Video]:
    query = db.query(Video)

    if folder_id:
        query = query.filter(Video.folder_id == folder_id)
    elif case_id:
        folder_ids = [f.id for f in db.query(Folder.id).filter(Folder.case_id == case_id)]
        query = query.filter(Video.folder_id.in_(folder_ids))

    if metadata_field and metadata_value is not None:
        query = query.filter(
            cast(Video.metadata_fields[metadata_field], String) == f'"{metadata_value}"'
        )

    if q:
        like = f"%{q}%"
        transcript_video_ids = [
            row.video_id
            for row in db.query(Transcript.video_id).filter(
                cast(Transcript.segments, String).ilike(like)
            )
        ]
        query = query.filter(
            or_(
                Video.filename.ilike(like),
                cast(Video.metadata_fields, String).ilike(like),
                Video.id.in_(transcript_video_ids) if transcript_video_ids else False,
            )
        )

    return query.order_by(Video.uploaded_at.desc()).limit(200).all()
