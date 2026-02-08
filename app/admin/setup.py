"""sqladmin setup with session-based auth."""

from fastapi import FastAPI
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.config import settings
from app.database import engine


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


def setup_admin(app: FastAPI) -> Admin:
    """Configure sqladmin and register all views."""
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
