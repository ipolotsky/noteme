import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_id", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id")
    )
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(255), unique=True
    )
    provider_payment_charge_id: Mapped[str] = mapped_column(String(255))
    amount_stars: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="completed")

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]  # noqa: F821
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="payments")  # type: ignore[name-defined]  # noqa: F821
