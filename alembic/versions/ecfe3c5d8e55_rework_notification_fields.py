"""Rework notification fields

Revision ID: ecfe3c5d8e55
Revises: 23ff32e98e49
Create Date: 2026-03-06 12:35:51.263094
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'ecfe3c5d8e55'
down_revision: Union[str, None] = '23ff32e98e49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('notify_day_before', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('users', sa.Column('notify_day_before_time', sa.Time(), server_default=sa.text("'09:00:00'"), nullable=False))
    op.add_column('users', sa.Column('notify_week_before', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('users', sa.Column('notify_week_before_time', sa.Time(), server_default=sa.text("'09:00:00'"), nullable=False))
    op.add_column('users', sa.Column('notify_weekly_digest', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('users', sa.Column('weekly_digest_day', sa.Integer(), server_default=sa.text('6'), nullable=False))
    op.add_column('users', sa.Column('weekly_digest_time', sa.Time(), server_default=sa.text("'19:00:00'"), nullable=False))

    op.execute("UPDATE users SET notify_day_before_time = notification_time, notify_week_before_time = notification_time")

    op.drop_index(op.f('ix_users_notification_filter'), table_name='users')
    op.drop_column('users', 'notification_count')
    op.drop_column('users', 'notification_time')


def downgrade() -> None:
    op.add_column('users', sa.Column('notification_time', sa.Time(), server_default=sa.text("'09:00:00'"), autoincrement=False, nullable=False))
    op.add_column('users', sa.Column('notification_count', sa.INTEGER(), server_default=sa.text('3'), autoincrement=False, nullable=False))

    op.execute("UPDATE users SET notification_time = notify_day_before_time")

    op.create_index(op.f('ix_users_notification_filter'), 'users', ['is_active', 'notifications_enabled', 'notification_time'], unique=False)
    op.drop_column('users', 'weekly_digest_time')
    op.drop_column('users', 'weekly_digest_day')
    op.drop_column('users', 'notify_weekly_digest')
    op.drop_column('users', 'notify_week_before_time')
    op.drop_column('users', 'notify_week_before')
    op.drop_column('users', 'notify_day_before_time')
    op.drop_column('users', 'notify_day_before')
