import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RedactionType(str, enum.Enum):
    FACE_AUTO = "face_auto"
    FACE_TRACKED = "face_tracked"
    MANUAL_REGION = "manual_region"
    AUDIO_MUTE = "audio_mute"
    TRANSCRIPT_BASED_AUDIO = "transcript_based_audio"


class RedactionJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class RedactionJob(Base):
    """One redaction run against a video. `regions` holds per-frame or
    tracked boxes for visual redaction; `audio_segments` holds [start,end]
    ranges to mute for audio redaction. Producing `result_version_id` creates
    a new immutable VideoVersion rather than mutating the source."""

    __tablename__ = "redaction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"), index=True)
    source_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("video_versions.id"))

    type: Mapped[RedactionType] = mapped_column(Enum(RedactionType))
    status: Mapped[RedactionJobStatus] = mapped_column(
        Enum(RedactionJobStatus), default=RedactionJobStatus.PENDING
    )

    # [{track_id, label, frames: [{frame|t, x, y, w, h}]}]
    regions: Mapped[list] = mapped_column(JSON, default=list)
    # [{start, end, reason}]
    audio_segments: Mapped[list] = mapped_column(JSON, default=list)

    result_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_versions.id"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
