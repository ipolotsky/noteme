import uuid
from datetime import datetime

from pydantic import BaseModel


class TagCreate(BaseModel):
    name: str


class TagUpdate(BaseModel):
    name: str


class TagRead(BaseModel):
    id: uuid.UUID
    user_id: int
    name: str
    created_at: datetime
    events_count: int = 0
    notes_count: int = 0

    model_config = {"from_attributes": True}
