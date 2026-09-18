import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatermarkScope(str, enum.Enum):
    GLOBAL = "global"
    USER = "user"


class Watermark(Base):
    """Admin- or user-configured watermark template. `template` supports
    placeholders: {viewer_name}, {viewer_email}, {timestamp}, {case_name}."""

    __tablename__ = "watermarks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[WatermarkScope] = mapped_column(Enum(WatermarkScope), default=WatermarkScope.GLOBAL)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    template: Mapped[str] = mapped_column(String(500), default="{viewer_name} • {timestamp}")
    enabled_for_playback: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled_for_export: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
