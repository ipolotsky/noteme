import uuid
from datetime import date, datetime

from pydantic import BaseModel


class EventBase(BaseModel):
    title: str
    event_date: date
    description: str | None = None


class EventCreate(EventBase):
    tag_names: list[str] = []
    is_system: bool = False


class EventUpdate(BaseModel):
    title: str | None = None
    event_date: date | None = None
    description: str | None = None
    tag_names: list[str] | None = None


class EventRead(EventBase):
    id: uuid.UUID
    user_id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime | None
    tags: list["TagBrief"] = []

    model_config = {"from_attributes": True}


class TagBrief(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}
