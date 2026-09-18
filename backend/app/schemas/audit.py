import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_label: str | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    details: dict
    timestamp: datetime

    model_config = {"from_attributes": True}
