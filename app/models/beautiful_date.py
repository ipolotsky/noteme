import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BeautifulDate(Base):
    __tablename__ = "beautiful_dates"
    __table_args__ = (
        Index("ix_beautiful_dates_event_target", "event_id", "target_date"),
        Index("ix_beautiful_dates_target", "target_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beautiful_date_strategies.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    label_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    label_en: Mapped[str] = mapped_column(String(500), nullable=False)
    interval_value: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    compound_parts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    share_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="beautiful_dates")  # type: ignore[name-defined]  # noqa: F821
    strategy: Mapped["BeautifulDateStrategy"] = relationship(back_populates="beautiful_dates")  # type: ignore[name-defined]  # noqa: F821
