"""add performance indexes

Revision ID: a3f8b2d41e57
Revises: 972b79f10c29
Create Date: 2026-02-07 23:30:00.000000
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f8b2d41e57'
down_revision: str | None = '972b79f10c29'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index('ix_events_user_id', 'events', ['user_id'])
    op.create_index('ix_notes_user_id', 'notes', ['user_id'])
    op.create_index(
        'ix_notes_reminder_lookup', 'notes',
        ['user_id', 'reminder_date', 'reminder_sent'],
    )
    op.create_index('ix_notification_log_user_id', 'notification_log', ['user_id'])
    op.create_index(
        'ix_users_notification_filter', 'users',
        ['is_active', 'notifications_enabled', 'notification_time'],
    )


def downgrade() -> None:
    op.drop_index('ix_users_notification_filter', table_name='users')
    op.drop_index('ix_notification_log_user_id', table_name='notification_log')
    op.drop_index('ix_notes_reminder_lookup', table_name='notes')
    op.drop_index('ix_notes_user_id', table_name='notes')
    op.drop_index('ix_events_user_id', table_name='events')
