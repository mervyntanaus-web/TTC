import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Transcript(Base):
    """ASR-generated transcript for a video's audio track. `segments` is
    [{id, start, end, text, speaker, redacted: bool}]. Editing/redacting a
    segment here is what transcript-based audio redaction acts on."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"), index=True, unique=True)
    segments: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str | None] = mapped_column(default=None)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
