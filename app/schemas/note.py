import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.event import TagBrief


class NoteBase(BaseModel):
    text: str
    reminder_date: date | None = None


class NoteCreate(NoteBase):
    tag_names: list[str] = []


class NoteUpdate(BaseModel):
    text: str | None = None
    reminder_date: date | None = None
    tag_names: list[str] | None = None


class NoteRead(NoteBase):
    id: uuid.UUID
    user_id: int
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime | None
    tags: list[TagBrief] = []
    has_media: bool = False

    model_config = {"from_attributes": True}
