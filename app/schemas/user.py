from datetime import datetime, time

from pydantic import BaseModel


class UserBase(BaseModel):
    first_name: str = ""
    language: str = "ru"
    timezone: str = "Europe/Moscow"
    notifications_enabled: bool = True
    notify_day_before: bool = True
    notify_day_before_time: time = time(9, 0)
    notify_week_before: bool = True
    notify_week_before_time: time = time(9, 0)
    notify_weekly_digest: bool = True
    weekly_digest_day: int = 6
    weekly_digest_time: time = time(19, 0)
    spoiler_enabled: bool = False


class UserCreate(UserBase):
    id: int  # Telegram user_id
    username: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    username: str | None = None
    language: str | None = None
    timezone: str | None = None
    notifications_enabled: bool | None = None
    notify_day_before: bool | None = None
    notify_day_before_time: time | None = None
    notify_week_before: bool | None = None
    notify_week_before_time: time | None = None
    notify_weekly_digest: bool | None = None
    weekly_digest_day: int | None = None
    weekly_digest_time: time | None = None
    spoiler_enabled: bool | None = None
    onboarding_completed: bool | None = None


class UserRead(UserBase):
    id: int
    username: str | None
    max_events: int
    max_wishes: int
    max_people_per_entity: int
    onboarding_completed: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
