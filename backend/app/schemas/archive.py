import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.video import StorageTier


class StorageTierEventOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    tier: StorageTier
    moved_at: datetime
    restore_eta: datetime | None

    model_config = {"from_attributes": True}
