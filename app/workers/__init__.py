"""arq worker setup and task definitions."""

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.workers.ai_logs import persist_ai_logs_task
from app.workers.notifications import check_and_send_notifications


def parse_redis_url() -> RedisSettings:
    """Parse NOTEME_REDIS_* settings into arq RedisSettings."""
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
        password=settings.redis_password,
    )


class WorkerSettings:
    """arq worker configuration."""

    redis_settings = parse_redis_url()

    functions = [
        "app.workers.beautiful_dates.recalculate_event_task",
        "app.workers.beautiful_dates.recalculate_all_task",
        "app.workers.notifications.send_digest_task",
        "app.workers.notifications.send_note_reminders_task",
        "app.workers.notifications.check_and_send_notifications",
        "app.workers.ai_logs.persist_ai_logs_task",
    ]

    cron_jobs = [
        cron(check_and_send_notifications, minute=set(range(60))),
        cron(persist_ai_logs_task, minute=set(range(60))),  # Drain AI logs every minute
    ]
