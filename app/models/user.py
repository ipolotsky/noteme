from datetime import datetime, time

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_notification_filter",
            "is_active", "notifications_enabled", "notification_time",
        ),
    )

    # Telegram user_id as PK (BIGINT, not UUID)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(5), default="ru")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")

    # Notification settings
    notification_time: Mapped[time] = mapped_column(
        Time, default=time(9, 0)
    )
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_count: Mapped[int] = mapped_column(Integer, default=3)

    # Limits (future monetization)
    max_events: Mapped[int] = mapped_column(Integer, default=10)
    max_notes: Mapped[int] = mapped_column(Integer, default=10)
    max_tags_per_entity: Mapped[int] = mapped_column(Integer, default=3)

    # Features
    spoiler_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Shared access (list of user_ids who can see this user's data)
    shared_with: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    tags: Mapped[list["Tag"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
    events: Mapped[list["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
    notes: Mapped[list["Note"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]  # noqa: F821
