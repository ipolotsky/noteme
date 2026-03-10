from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscription_plans"

    name_ru: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    description_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_months: Mapped[int] = mapped_column(Integer, default=1)
    price_stars: Mapped[int] = mapped_column(Integer)
    is_lifetime: Mapped[bool] = mapped_column(Boolean, default=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")  # type: ignore[name-defined]  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(back_populates="plan")  # type: ignore[name-defined]  # noqa: F821
