import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RetentionPolicy(Base):
    """Retention rule for a category (e.g. "standard", "major_incident",
    "litigation_hold"). `retention_days` drives automatic expiry
    calculation; `auto_delete` gates whether the lifecycle sweep actually
    deletes on expiry or only flags for review."""

    __tablename__ = "retention_policies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(100), unique=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    auto_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_archive_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
