import uuid
from datetime import datetime

from pydantic import BaseModel


class RetentionPolicyUpsert(BaseModel):
    category: str
    retention_days: int
    auto_delete: bool = False
    auto_archive_after_days: int | None = None
    description: str | None = None


class RetentionPolicyOut(BaseModel):
    id: uuid.UUID
    category: str
    retention_days: int
    auto_delete: bool
    auto_archive_after_days: int | None
    description: str | None

    model_config = {"from_attributes": True}


class RetentionStatusOut(BaseModel):
    category: str
    expires_at: datetime
    archive_at: datetime | None
    legal_hold: bool
    eligible_for_deletion: bool
    eligible_for_archive: bool


class LegalHoldUpdate(BaseModel):
    legal_hold: bool


class SweepResultOut(BaseModel):
    archived: list[uuid.UUID]
    deleted: list[uuid.UUID]
