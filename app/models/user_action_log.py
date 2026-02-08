"""User action log model — tracks all user actions in the bot."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserActionLog(Base):
    __tablename__ = "user_action_logs"
    __table_args__ = (
        Index("ix_user_action_logs_user_id", "user_id"),
        Index("ix_user_action_logs_created_at", "created_at"),
        Index("ix_user_action_logs_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g. "start", "create_event", "delete_note", "view_feed", "ai_message", "change_settings"
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
