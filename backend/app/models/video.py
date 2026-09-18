import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VideoStatus(str, enum.Enum):
    INGESTED = "ingested"
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_VENDOR_DECODER = "needs_vendor_decoder"
    FAILED = "failed"
    DELETED = "deleted"


class StorageTier(str, enum.Enum):
    HOT = "hot"
    COLD = "cold"
    RESTORING = "restoring"


class Video(Base):
    """A single piece of video evidence. The immutable original bytes live in
    the `original` VideoVersion; this row is the catalog/metadata record that
    everything else (search, playback, redaction, sharing, retention) hangs off."""

    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("folders.id"), index=True)

    filename: Mapped[str] = mapped_column(String(500))
    format: Mapped[str] = mapped_column(String(20))
    source_connector: Mapped[str] = mapped_column(String(100), default="manual_upload")
    camera_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.INGESTED)
    storage_tier: Mapped[StorageTier] = mapped_column(Enum(StorageTier), default=StorageTier.HOT)

    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

    captured_at: Mapped[datetime | None] = mapped_column(nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    metadata_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    retention_category: Mapped[str] = mapped_column(String(100), default="standard")
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class VideoVersionKind(str, enum.Enum):
    ORIGINAL = "original"
    REDACTED = "redacted"
    DISCLOSURE = "disclosure"


class VideoVersion(Base):
    """Immutable rendered artifact of a Video. `original` is created once at
    ingestion and never overwritten; subsequent redaction/disclosure runs each
    create a new version, enabling reopen/correct/republish workflows."""

    __tablename__ = "video_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"), index=True)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_versions.id"), nullable=True
    )

    kind: Mapped[VideoVersionKind] = mapped_column(Enum(VideoVersionKind))
    storage_key: Mapped[str] = mapped_column(String(1000))
    storage_tier: Mapped[StorageTier] = mapped_column(Enum(StorageTier), default=StorageTier.HOT)

    redaction_job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    watermark_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
