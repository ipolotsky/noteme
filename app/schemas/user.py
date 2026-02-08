from datetime import datetime, time

from pydantic import BaseModel


class UserBase(BaseModel):
    first_name: str = ""
    language: str = "ru"
    timezone: str = "Europe/Moscow"
    notification_time: time = time(9, 0)
    notifications_enabled: bool = True
    notification_count: int = 3
    spoiler_enabled: bool = False


class UserCreate(UserBase):
    id: int  # Telegram user_id
    username: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    username: str | None = None
    language: str | None = None
    timezone: str | None = None
    notification_time: time | None = None
    notifications_enabled: bool | None = None
    notification_count: int | None = None
    spoiler_enabled: bool | None = None
    onboarding_completed: bool | None = None


class UserRead(UserBase):
    id: int
    username: str | None
    max_events: int
    max_notes: int
    max_tags_per_entity: int
    onboarding_completed: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
