import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.video import StorageTier


class StorageTierEvent(Base):
    """History of hot/cold tier transitions for a video, for archive/restore
    auditability and the ≤24h restore SLA demo."""

    __tablename__ = "storage_tier_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"), index=True)
    tier: Mapped[StorageTier] = mapped_column(Enum(StorageTier))
    moved_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    restore_eta: Mapped[datetime | None] = mapped_column(nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
