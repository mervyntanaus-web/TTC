import uuid
from datetime import datetime

from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    id: str
    start: float
    end: float
    text: str
    speaker: str | None = None
    redacted: bool = False


class TranscriptOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    segments: list[TranscriptSegment]
    language: str | None
    edited: bool
    generated_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptSegmentUpdate(BaseModel):
    text: str | None = None
    redacted: bool | None = None


class GenerateTranscriptRequest(BaseModel):
    version_id: uuid.UUID
