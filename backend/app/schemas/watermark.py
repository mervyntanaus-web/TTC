import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.watermark import WatermarkScope


class WatermarkUpsert(BaseModel):
    template: str = "{viewer_name} • {timestamp}"
    enabled_for_playback: bool = True
    enabled_for_export: bool = True


class WatermarkOut(BaseModel):
    id: uuid.UUID
    scope: WatermarkScope
    user_id: uuid.UUID | None
    template: str
    enabled_for_playback: bool
    enabled_for_export: bool
    created_at: datetime

    model_config = {"from_attributes": True}
