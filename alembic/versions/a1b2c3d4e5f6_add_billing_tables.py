"""Add billing tables

Revision ID: a1b2c3d4e5f6
Revises: ecfe3c5d8e55
Create Date: 2026-03-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "ecfe3c5d8e55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )

    op.create_table(
        "subscription_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name_ru", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("description_ru", sa.Text, nullable=True),
        sa.Column("description_en", sa.Text, nullable=True),
        sa.Column("duration_months", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price_stars", sa.Integer, nullable=False),
        sa.Column("is_lifetime", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("discount_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_lifetime", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(50), nullable=False, server_default="payment"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_subscriptions_user_active", "subscriptions", ["user_id", "is_active"])

    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(255), nullable=False, unique=True),
        sa.Column("provider_payment_charge_id", sa.String(255), nullable=False),
        sa.Column("amount_stars", sa.Integer, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    op.create_table(
        "referral_rewards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reward_months", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "users",
        sa.Column("referred_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.execute("""
        UPDATE beautiful_date_strategies
        SET params = jsonb_set(params, '{max}', '400')
        WHERE name_en = 'Round hundreds of days'
          AND (params->>'max')::int != 400
    """)
    op.execute("""
        UPDATE beautiful_date_strategies
        SET params = jsonb_set(params, '{min}', '11000')
        WHERE name_en = 'Round thousands of days'
          AND (params->>'min')::int != 11000
    """)

    op.execute("INSERT INTO app_settings (key, value, description) VALUES ('default_max_events', '10', 'Default event limit for new users') ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO app_settings (key, value, description) VALUES ('default_max_wishes', '10', 'Default wish limit for new users') ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO app_settings (key, value, description) VALUES ('default_max_people_per_entity', '3', 'Default people per event/wish limit') ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO app_settings (key, value, description) VALUES ('referral_reward_months', '1', 'Months of subscription granted for referral') ON CONFLICT DO NOTHING")


def downgrade() -> None:
    op.drop_column("users", "referred_by")
    op.drop_table("referral_rewards")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_user_active", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("app_settings")

    op.execute("""
        UPDATE beautiful_date_strategies
        SET params = jsonb_set(params, '{max}', '1000')
        WHERE name_en = 'Round hundreds of days'
    """)
    op.execute("""
        UPDATE beautiful_date_strategies
        SET params = jsonb_set(params, '{min}', '1000')
        WHERE name_en = 'Round thousands of days'
    """)
