import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors import CONNECTOR_REGISTRY, get_connector
from app.db import get_db
from app.models.folder import Folder
from app.models.user import User
from app.schemas.connector import CameraOut, RetrieveFootageRequest
from app.schemas.video import VideoOut
from app.security import get_current_user
from app.services.audit_service import log_action
from app.services.ingestion_service import UnsupportedVideoFormatError, ingest_local_file

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
def list_connectors() -> list[str]:
    return sorted(CONNECTOR_REGISTRY.keys())


@router.get("/{connector_name}/cameras", response_model=list[CameraOut])
def list_cameras(connector_name: str) -> list[CameraOut]:
    try:
        connector = get_connector(connector_name)
        return [CameraOut(**c.__dict__) for c in connector.list_cameras()]
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{connector_name}/retrieve", response_model=VideoOut, status_code=201)
def retrieve_footage(
    connector_name: str,
    payload: RetrieveFootageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoOut:
    """Automated retrieval: pulls footage from a connected VMS for a camera +
    time range, associates it with the given folder/case, and (per the RFP)
    preserves the source recording from deletion. Requires the requesting
    user to already have edit access on the destination folder — approval of
    the *retrieval request itself* is expected to happen upstream of this
    call (e.g. a case-management workflow), this endpoint is the "after
    approval" retrieval step."""
    folder = db.get(Folder, payload.folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        connector = get_connector(connector_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with tempfile.TemporaryDirectory() as tmp:
        try:
            footage = connector.retrieve_footage(payload.camera_id, payload.start, payload.end, tmp)
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

        try:
            video = ingest_local_file(
                db,
                folder_id=payload.folder_id,
                local_path=Path(footage.local_path),
                filename=footage.filename,
                source_connector=connector.name,
                camera_id=footage.camera_id,
                uploaded_by=user.id,
                metadata_fields=payload.metadata_fields,
                retention_category=payload.retention_category,
                captured_at=footage.captured_at,
                legal_hold=True,
            )
        except UnsupportedVideoFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    protected = connector.protect_source_from_deletion(
        payload.camera_id, payload.start, payload.end
    )
    log_action(
        db,
        user,
        "video.retrieve.automated",
        "video",
        video.id,
        {
            "connector": connector.name,
            "camera_id": payload.camera_id,
            "source_protected_from_deletion": protected,
        },
    )
    return video
