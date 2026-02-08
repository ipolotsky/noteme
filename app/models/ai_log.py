"""AI request/response log model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AILog(Base):
    __tablename__ = "ai_logs"
    __table_args__ = (
        Index("ix_ai_logs_user_id", "user_id"),
        Index("ix_ai_logs_created_at", "created_at"),
        Index("ix_ai_logs_agent_name", "agent_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # validation, router, event_agent, note_agent, query_agent, whisper
    model: Mapped[str] = mapped_column(String(50), nullable=False)  # gpt-4o-mini, whisper-1
    request_messages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
