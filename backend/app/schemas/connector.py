import uuid
from datetime import datetime

from pydantic import BaseModel


class CameraOut(BaseModel):
    camera_id: str
    name: str
    location: str | None = None


class RetrieveFootageRequest(BaseModel):
    camera_id: str
    start: datetime
    end: datetime
    folder_id: uuid.UUID
    retention_category: str = "standard"
    metadata_fields: dict = {}
