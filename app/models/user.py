from datetime import datetime, time

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(5), default="ru")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")

    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_day_before: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_day_before_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    notify_week_before: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_week_before_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    notify_weekly_digest: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_digest_day: Mapped[int] = mapped_column(Integer, default=6)
    weekly_digest_time: Mapped[time] = mapped_column(Time, default=time(19, 0))

    max_events: Mapped[int] = mapped_column(Integer, default=10)
    max_wishes: Mapped[int] = mapped_column(Integer, default=10)
    max_people_per_entity: Mapped[int] = mapped_column(Integer, default=3)

    spoiler_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    referred_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    shared_with: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    people: Mapped[list["Person"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
    events: Mapped[list["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
    wishes: Mapped[list["Wish"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
