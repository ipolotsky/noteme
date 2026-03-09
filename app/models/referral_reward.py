from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReferralReward(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "referral_rewards"

    referrer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    referred_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    reward_months: Mapped[int] = mapped_column(Integer)

    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_id])  # type: ignore[name-defined]  # noqa: F821
    referred: Mapped["User"] = relationship(foreign_keys=[referred_id])  # type: ignore[name-defined]  # noqa: F821
