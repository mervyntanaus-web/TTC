import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.share import RecipientType, ShareResourceType, ShareScope


class ShareLinkCreate(BaseModel):
    resource_type: ShareResourceType
    resource_id: uuid.UUID
    scope: ShareScope = ShareScope.VIEW_ONLY
    recipient_type: RecipientType
    recipient_label: str | None = None
    expires_in_days: int | None = 7


class ShareLinkOut(BaseModel):
    id: uuid.UUID
    resource_type: ShareResourceType
    resource_id: uuid.UUID
    token: str
    scope: ShareScope
    recipient_type: RecipientType
    recipient_label: str | None
    created_at: datetime
    expires_at: datetime | None
    revoked: bool
    access_count: int
    last_accessed_at: datetime | None

    model_config = {"from_attributes": True}
