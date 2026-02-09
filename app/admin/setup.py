"""sqladmin setup with session-based auth + clear-db action + test notifications."""

import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from app.config import settings
from app.database import async_session_factory, engine

logger = logging.getLogger(__name__)


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({"authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("authenticated", False)


# Tables to truncate (in FK-safe order, CASCADE handles the rest)
_CLEAR_TABLES = [
    "media_links",
    "note_tags",
    "event_tags",
    "beautiful_dates",
    "notification_logs",
    "ai_logs",
    "user_action_logs",
    "notes",
    "events",
    "tags",
]


def setup_admin(app: FastAPI) -> Admin:
    """Configure sqladmin and register all views."""

    # Session middleware needed by custom endpoints below.
    # Admin() also adds it, but double middleware is harmless.
    app.add_middleware(SessionMiddleware, secret_key=settings.admin_secret_key)

    # --- Custom endpoints MUST be registered BEFORE Admin() mount ---

    @app.get("/admin/clear-db", response_class=HTMLResponse)
    async def clear_db_page(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>Clear Database</h2>"
            "<p>This will delete all events, notes, tags, media links, and logs.</p>"
            "<p>Users and strategies will be kept.</p>"
            "<form method='POST'>"
            "<button type='submit' style='padding:12px 32px;font-size:16px;"
            "background:#dc3545;color:#fff;border:none;border-radius:6px;cursor:pointer'>"
            "Clear Database</button></form>"
            "<br><a href='/admin'>Cancel</a>"
            "</body></html>"
        )

    @app.post("/admin/clear-db")
    async def clear_db_action(request: Request) -> RedirectResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)

        async with async_session_factory() as session:
            for table in _CLEAR_TABLES:
                await session.execute(text(f"DELETE FROM {table}"))  # noqa: S608
            await session.commit()

        logger.warning("[admin] Database cleared by admin")
        return RedirectResponse(url="/admin", status_code=302)

    @app.get("/admin/test-notify/{user_id}", response_class=HTMLResponse)
    async def test_notify_page(request: Request, user_id: int) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            f"<h2>Test Notifications</h2>"
            f"<p>Send test digest + note reminders to user <b>{user_id}</b>?</p>"
            f"<form method='POST'>"
            "<button type='submit' style='padding:12px 32px;font-size:16px;"
            "background:#0d6efd;color:#fff;border:none;border-radius:6px;cursor:pointer'>"
            "Send Test Notification</button></form>"
            "<br><a href='/admin'>Cancel</a>"
            "</body></html>"
        )

    @app.post("/admin/test-notify/{user_id}", response_class=HTMLResponse)
    async def test_notify_action(request: Request, user_id: int) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from arq import create_pool

        from app.workers import parse_redis_url

        try:
            pool = await create_pool(parse_redis_url())
            await pool.enqueue_job("app.workers.notifications.send_digest_task", user_id, True)
            await pool.enqueue_job("app.workers.notifications.send_note_reminders_task", user_id, True)
            await pool.close()
            status = f"Jobs enqueued for user <b>{user_id}</b>. Check bot chat for results."
        except Exception:
            logger.exception("[admin] Failed to enqueue test notification jobs")
            status = "Error: failed to enqueue jobs. Is Redis running?"

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            f"<h2>Test Notifications</h2>"
            f"<p>{status}</p>"
            f"<br><a href='/admin/user/details/{user_id}'>Back to user</a>"
            " | <a href='/admin'>Admin home</a>"
            "</body></html>"
        )

    # --- Now mount sqladmin (catches remaining /admin/* paths) ---

    auth_backend = AdminAuth(secret_key=settings.admin_secret_key)
    admin = Admin(
        app,
        engine,
        authentication_backend=auth_backend,
        title="Noteme Admin",
    )

    from app.admin.views import (
        AILogAdmin,
        BeautifulDateAdmin,
        BeautifulDateStrategyAdmin,
        EventAdmin,
        NoteAdmin,
        NotificationLogAdmin,
        TagAdmin,
        UserActionLogAdmin,
        UserAdmin,
    )

    admin.add_view(UserAdmin)
    admin.add_view(EventAdmin)
    admin.add_view(NoteAdmin)
    admin.add_view(TagAdmin)
    admin.add_view(BeautifulDateStrategyAdmin)
    admin.add_view(BeautifulDateAdmin)
    admin.add_view(NotificationLogAdmin)
    admin.add_view(AILogAdmin)
    admin.add_view(UserActionLogAdmin)

    return admin
