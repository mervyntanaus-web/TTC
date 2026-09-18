import uuid
from datetime import datetime

from pydantic import BaseModel


class FolderCreate(BaseModel):
    case_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    metadata_fields: dict = {}
    linked_folder_ids: list[uuid.UUID] = []


class FolderUpdate(BaseModel):
    name: str | None = None
    metadata_fields: dict | None = None
    linked_folder_ids: list[uuid.UUID] | None = None


class FolderOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    metadata_fields: dict
    linked_folder_ids: list
    created_at: datetime

    model_config = {"from_attributes": True}


class FolderPermissionSet(BaseModel):
    user_id: uuid.UUID | None = None
    role: str | None = None
    can_view: bool = True
    can_edit: bool = False
    can_download: bool = False
    can_share: bool = False


class CaseCreate(BaseModel):
    name: str
    description: str | None = None
    retention_category: str = "standard"
    metadata_fields: dict = {}


class CaseOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    retention_category: str
    metadata_fields: dict
    created_at: datetime

    model_config = {"from_attributes": True}
