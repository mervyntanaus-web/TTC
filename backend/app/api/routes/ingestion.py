import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_folder_access
from app.db import get_db
from app.models.folder import Folder
from app.models.user import User
from app.schemas.video import VideoOut
from app.security import get_current_user
from app.services.audit_service import log_action
from app.services.ingestion_service import UnsupportedVideoFormatError, ingest_local_file

router = APIRouter(prefix="/videos", tags=["ingestion"])


def _save_upload(upload: UploadFile, tmp_dir: Path) -> Path:
    dest = tmp_dir / upload.filename
    with open(dest, "wb") as fh:
        while chunk := upload.file.read(8 * 1024 * 1024):
            fh.write(chunk)
    return dest


@router.post("/upload", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def upload_video(
    file: UploadFile = File(...),
    folder_id: uuid.UUID = Form(...),
    metadata_fields: str = Form("{}"),
    retention_category: str = Form("standard"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoOut:
    """Manual video upload — used both for direct staff uploads and for the
    RFP's "manual retrieval" flow when a source VMS isn't connected. Access
    is folder-scoped: the caller needs edit permission on the destination
    folder."""
    require_folder_access("edit")(
        folder=_get_folder(db, folder_id), user=user, db=db
    )
    try:
        parsed_metadata = json.loads(metadata_fields)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata_fields must be valid JSON") from exc

    with tempfile.TemporaryDirectory() as tmp:
        local_path = _save_upload(file, Path(tmp))
        try:
            video = ingest_local_file(
                db,
                folder_id=folder_id,
                local_path=local_path,
                filename=file.filename,
                source_connector="manual_upload",
                uploaded_by=user.id,
                metadata_fields=parsed_metadata,
                retention_category=retention_category,
            )
        except UnsupportedVideoFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_action(
        db,
        user,
        "video.upload.manual",
        "video",
        video.id,
        {"filename": video.filename, "folder_id": str(folder_id)},
    )
    return video


@router.post("/bulk-upload", response_model=list[VideoOut], status_code=status.HTTP_201_CREATED)
def bulk_upload_videos(
    files: list[UploadFile] = File(...),
    folder_id: uuid.UUID = Form(...),
    metadata_fields: str = Form("{}"),
    retention_category: str = Form("standard"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[VideoOut]:
    """Bulk upload of multiple files into a single folder in one request, per
    the RFP's "support bulk upload of files" requirement."""
    require_folder_access("edit")(folder=_get_folder(db, folder_id), user=user, db=db)
    try:
        parsed_metadata = json.loads(metadata_fields)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata_fields must be valid JSON") from exc

    results: list[VideoOut] = []
    errors: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for upload in files:
            local_path = _save_upload(upload, Path(tmp))
            try:
                video = ingest_local_file(
                    db,
                    folder_id=folder_id,
                    local_path=local_path,
                    filename=upload.filename,
                    source_connector="manual_upload",
                    uploaded_by=user.id,
                    metadata_fields=parsed_metadata,
                    retention_category=retention_category,
                )
                results.append(video)
                log_action(
                    db, user, "video.upload.bulk", "video", video.id, {"filename": video.filename}
                )
            except UnsupportedVideoFormatError as exc:
                errors.append({"filename": upload.filename, "error": str(exc)})

    if errors and not results:
        raise HTTPException(status_code=400, detail={"errors": errors})
    return results


def _get_folder(db: Session, folder_id: uuid.UUID) -> Folder:
    folder = db.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder
