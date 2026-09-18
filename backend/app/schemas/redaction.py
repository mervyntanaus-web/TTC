import uuid

from pydantic import BaseModel

from app.models.redaction import RedactionJobStatus, RedactionType


class RegionFrame(BaseModel):
    t: float  # seconds into the clip
    x: float
    y: float
    w: float
    h: float


class RegionTrack(BaseModel):
    track_id: str
    label: str | None = None
    frames: list[RegionFrame]


class AudioSegment(BaseModel):
    start: float
    end: float
    reason: str | None = None


class AutoTrackRequest(BaseModel):
    """User clicks a face once at time `t` with an initial box; the server
    runs a CSRT tracker forward from there to produce a full track."""

    version_id: uuid.UUID
    start_t: float
    x: float
    y: float
    w: float
    h: float
    label: str | None = None
    max_seconds: float | None = None


class DetectFacesRequest(BaseModel):
    version_id: uuid.UUID
    sample_every_seconds: float = 1.0


class RedactionJobCreate(BaseModel):
    video_id: uuid.UUID
    source_version_id: uuid.UUID
    type: RedactionType
    regions: list[RegionTrack] = []
    audio_segments: list[AudioSegment] = []


class RedactionJobOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    source_version_id: uuid.UUID
    type: RedactionType
    status: RedactionJobStatus
    regions: list
    audio_segments: list
    result_version_id: uuid.UUID | None
    error_message: str | None

    model_config = {"from_attributes": True}
