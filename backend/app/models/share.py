import enum
import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ShareResourceType(str, enum.Enum):
    VIDEO = "video"
    FOLDER = "folder"


class ShareScope(str, enum.Enum):
    VIEW_ONLY = "view_only"
    DOWNLOAD = "download"


class RecipientType(str, enum.Enum):
    INTERNAL_STAFF = "internal_staff"
    LEGAL_TEAM = "legal_team"
    POLICE = "police"
    INSURANCE = "insurance"
    COURT = "court"
    FOI = "foi"
    GUEST = "guest"


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class ShareLink(Base):
    """A time-boxed, scoped access grant to a video or folder, for internal or
    external (police/insurance/court/FOI/guest) recipients. `token` is the
    unauthenticated bearer credential used on the public share endpoint."""

    __tablename__ = "share_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resource_type: Mapped[ShareResourceType] = mapped_column(Enum(ShareResourceType))
    resource_id: Mapped[uuid.UUID] = mapped_column(index=True)

    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_generate_token)
    scope: Mapped[ShareScope] = mapped_column(Enum(ShareScope), default=ShareScope.VIEW_ONLY)
    recipient_type: Mapped[RecipientType] = mapped_column(Enum(RecipientType))
    recipient_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    access_count: Mapped[int] = mapped_column(default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(nullable=True)
