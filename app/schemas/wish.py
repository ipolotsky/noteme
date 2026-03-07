import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.event import PersonBrief


class WishBase(BaseModel):
    text: str


class WishCreate(WishBase):
    person_names: list[str] = []


class WishUpdate(BaseModel):
    text: str | None = None
    person_names: list[str] | None = None


class WishRead(WishBase):
    id: uuid.UUID
    user_id: int
    created_at: datetime
    updated_at: datetime | None
    people: list[PersonBrief] = []
    has_media: bool = False

    model_config = {"from_attributes": True}
