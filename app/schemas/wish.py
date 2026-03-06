import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.event import PersonBrief


class WishBase(BaseModel):
    text: str
    reminder_date: date | None = None


class WishCreate(WishBase):
    person_names: list[str] = []


class WishUpdate(BaseModel):
    text: str | None = None
    reminder_date: date | None = None
    person_names: list[str] | None = None


class WishRead(WishBase):
    id: uuid.UUID
    user_id: int
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime | None
    people: list[PersonBrief] = []
    has_media: bool = False

    model_config = {"from_attributes": True}
