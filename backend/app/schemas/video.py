import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.video import StorageTier, VideoStatus, VideoVersionKind


class VideoOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    filename: str
    format: str
    source_connector: str
    camera_id: str | None
    status: VideoStatus
    storage_tier: StorageTier
    checksum_sha256: str | None
    size_bytes: int | None
    duration_seconds: float | None
    captured_at: datetime | None
    uploaded_at: datetime
    metadata_fields: dict
    retention_category: str
    legal_hold: bool

    model_config = {"from_attributes": True}


class VideoVersionOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    parent_version_id: uuid.UUID | None
    kind: VideoVersionKind
    storage_tier: StorageTier
    redaction_job_id: uuid.UUID | None
    watermark_applied: bool
    created_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


class VideoMetadataUpdate(BaseModel):
    metadata_fields: dict | None = None
    retention_category: str | None = None
    captured_at: datetime | None = None


class ManualUploadAssociate(BaseModel):
    folder_id: uuid.UUID
    case_reference: str | None = None
    metadata_fields: dict = {}
