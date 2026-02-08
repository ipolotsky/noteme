import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        Index("ix_notes_user_id", "user_id"),
        Index("ix_notes_reminder_lookup", "user_id", "reminder_date", "reminder_sent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reminder_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notes")  # type: ignore[name-defined]  # noqa: F821
    tags: Mapped[list["Tag"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        secondary="note_tags", back_populates="notes"
    )
    media_link: Mapped["MediaLink | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="note", uselist=False, cascade="all, delete-orphan"
    )


class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
