import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Folder(Base):
    """A folder or subfolder within a case. Self-referencing parent_id gives
    arbitrary nesting; `linked_folder_ids` supports "related folder linking"."""

    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("folders.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    metadata_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    linked_folder_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class FolderPermission(Base):
    """Folder-level ACL entry. File-level overrides live on Video.permissions."""

    __tablename__ = "folder_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    folder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("folders.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    can_view: Mapped[bool] = mapped_column(default=True)
    can_edit: Mapped[bool] = mapped_column(default=False)
    can_download: Mapped[bool] = mapped_column(default=False)
    can_share: Mapped[bool] = mapped_column(default=False)
