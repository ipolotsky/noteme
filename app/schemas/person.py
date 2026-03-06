import uuid
from datetime import datetime

from pydantic import BaseModel


class PersonCreate(BaseModel):
    name: str


class PersonUpdate(BaseModel):
    name: str


class PersonRead(BaseModel):
    id: uuid.UUID
    user_id: int
    name: str
    created_at: datetime
    events_count: int = 0
    wishes_count: int = 0

    model_config = {"from_attributes": True}
