import logging
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from sqladmin import Admin
from sqladmin._menu import ItemMenu
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import Date, cast, func, select, text
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


_CLEAR_TABLES = [
    "referral_rewards",
    "payments",
    "subscriptions",
    "media_links",
    "wish_people",
    "event_people",
    "beautiful_dates",
    "notification_logs",
    "ai_logs",
    "user_action_logs",
    "wishes",
    "events",
    "people",
]


def setup_admin(app: FastAPI) -> Admin:
    app.add_middleware(SessionMiddleware, secret_key=settings.admin_secret_key)

    @app.get("/admin")
    async def admin_index_redirect(request: Request) -> RedirectResponse:
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    @app.get("/admin/dashboard", response_class=HTMLResponse)
    async def dashboard_page(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from app.models.event import Event
        from app.models.payment import Payment
        from app.models.subscription import Subscription
        from app.models.user import User
        from app.models.wish import Wish
        from app.services.ai_cost_service import (
            get_current_month_stats,
            get_exchange_rates,
            get_monthly_stats,
        )

        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        async with async_session_factory() as session:
            total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
            new_users_7d = (
                await session.execute(
                    select(func.count(User.id)).where(User.created_at >= week_ago)
                )
            ).scalar() or 0
            new_users_30d = (
                await session.execute(
                    select(func.count(User.id)).where(User.created_at >= month_ago)
                )
            ).scalar() or 0

            paying_users = (
                await session.execute(
                    select(func.count(func.distinct(Subscription.user_id))).where(
                        Subscription.is_active.is_(True)
                    )
                )
            ).scalar() or 0
            free_users = total_users - paying_users

            total_stars = (
                await session.execute(select(func.coalesce(func.sum(Payment.amount_stars), 0)))
            ).scalar() or 0

            total_events = (await session.execute(select(func.count(Event.id)))).scalar() or 0
            total_wishes = (await session.execute(select(func.count(Wish.id)))).scalar() or 0

            avg_events = round(total_events / total_users, 1) if total_users else 0
            avg_wishes = round(total_wishes / total_users, 1) if total_users else 0
            wish_event_ratio = round(total_wishes / total_events, 2) if total_events else 0

            growth_rows = (
                await session.execute(
                    select(
                        cast(User.created_at, Date).label("day"),
                        func.count(User.id).label("cnt"),
                    )
                    .where(User.created_at >= month_ago)
                    .group_by(cast(User.created_at, Date))
                    .order_by(cast(User.created_at, Date))
                )
            ).all()

            growth_labels = [row.day.strftime("%d.%m") for row in growth_rows]
            growth_data: list[int] = []
            running = total_users - new_users_30d
            for row in growth_rows:
                running += row.cnt
                growth_data.append(running)

            ai_month = await get_current_month_stats(session)
            ai_monthly = await get_monthly_stats(session, months=6)

        rates = await get_exchange_rates()

        ai_avg_per_user = round(ai_month["tokens_total"] / total_users) if total_users else 0
        ai_avg_cost_per_user = ai_month["cost_usd"] / total_users if total_users else 0.0

        from app.services.ai_cost_service import STARS_PER_USD

        if paying_users > 0:
            min_price_stars = round(
                ai_month["cost_usd"] * STARS_PER_USD / paying_users, 1
            )
        else:
            min_price_stars = round(ai_month["cost_usd"] * STARS_PER_USD, 1)

        ai_monthly_labels = [m["month"] for m in ai_monthly]
        ai_monthly_tokens = [m["tokens_total"] for m in ai_monthly]
        ai_monthly_costs = [round(m["cost_usd"], 4) for m in ai_monthly]

        rendered = await request.app.state.admin.templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "total_users": total_users,
                "new_users_7d": new_users_7d,
                "new_users_30d": new_users_30d,
                "paying_users": paying_users,
                "free_users": free_users,
                "total_stars": total_stars,
                "total_events": total_events,
                "total_wishes": total_wishes,
                "avg_events": avg_events,
                "avg_wishes": avg_wishes,
                "wish_event_ratio": wish_event_ratio,
                "growth_labels": growth_labels,
                "growth_data": growth_data,
                "ai_month": ai_month,
                "rates": rates,
                "ai_avg_per_user": ai_avg_per_user,
                "ai_avg_cost_per_user": ai_avg_cost_per_user,
                "ai_monthly_labels": ai_monthly_labels,
                "ai_monthly_tokens": ai_monthly_tokens,
                "ai_monthly_costs": ai_monthly_costs,
                "min_price_stars": min_price_stars,
            },
        )
        return HTMLResponse(content=rendered.body, status_code=rendered.status_code)

    @app.get("/admin/ai-costs", response_class=HTMLResponse)
    async def ai_costs_page(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from app.services.ai_cost_service import (
            get_current_month_stats,
            get_exchange_rates,
            get_monthly_stats,
            get_users_token_stats,
        )

        page = int(request.query_params.get("page", 1))
        page_size = 50

        async with async_session_factory() as session:
            user_stats, total_users = await get_users_token_stats(
                session, page=page, page_size=page_size
            )
            monthly_stats = await get_monthly_stats(session, months=6)
            current_month = await get_current_month_stats(session)

        rates = await get_exchange_rates()

        monthly_labels = [m["month"] for m in monthly_stats]
        monthly_tokens = [m["tokens_total"] for m in monthly_stats]
        monthly_costs = [round(m["cost_usd"], 4) for m in monthly_stats]

        rendered = await request.app.state.admin.templates.TemplateResponse(
            request,
            "ai_costs.html",
            {
                "user_stats": user_stats,
                "total_users": total_users,
                "page": page,
                "page_size": page_size,
                "monthly_stats": monthly_stats,
                "current_month": current_month,
                "rates": rates,
                "monthly_labels": monthly_labels,
                "monthly_tokens": monthly_tokens,
                "monthly_costs": monthly_costs,
            },
        )
        return HTMLResponse(content=rendered.body, status_code=rendered.status_code)

    @app.get("/admin/stars-balance", response_class=HTMLResponse)
    async def stars_balance_page(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from app.bot import bot

        balance = 0
        transactions: list[dict] = []
        error = ""
        try:
            result = await bot.get_star_transactions(limit=100)
            balance = sum(t.amount if t.source else -t.amount for t in result.transactions)
            for t in result.transactions[:50]:
                incoming = t.source is not None
                transactions.append(
                    {
                        "id": t.id,
                        "amount": t.amount,
                        "incoming": incoming,
                        "date": t.date.strftime("%d.%m.%Y %H:%M"),
                    }
                )
        except Exception:
            logger.exception("[admin] Failed to get star transactions")
            error = "Failed to fetch data from Telegram API."

        rendered = await request.app.state.admin.templates.TemplateResponse(
            request,
            "stars_balance.html",
            {"balance": balance, "transactions": transactions, "error": error},
        )
        return HTMLResponse(content=rendered.body, status_code=rendered.status_code)

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
                await session.execute(text(f"DELETE FROM {table}"))
            await session.commit()

        logger.warning("[admin] Database cleared by admin")
        return RedirectResponse(url="/admin", status_code=302)

    @app.get("/admin/seed-strategies", response_class=HTMLResponse)
    async def seed_strategies_page(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from sqlalchemy import func, select

        from app.models.beautiful_date_strategy import BeautifulDateStrategy
        from app.utils.seed import STRATEGIES

        async with async_session_factory() as session:
            result = await session.execute(select(func.count(BeautifulDateStrategy.id)))
            current = result.scalar() or 0

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>Seed Strategies</h2>"
            f"<p>Current: <b>{current}</b> strategies in DB</p>"
            f"<p>Expected: <b>{len(STRATEGIES)}</b> strategies from code</p>"
            "<p>This will add any missing strategies without modifying existing ones.</p>"
            "<form method='POST'>"
            "<button type='submit' style='padding:12px 32px;font-size:16px;"
            "background:#198754;color:#fff;border:none;border-radius:6px;cursor:pointer'>"
            "Seed Missing Strategies</button></form>"
            "<br><a href='/admin/beautiful-date-strategy/list'>Back to strategies</a>"
            " | <a href='/admin'>Admin home</a>"
            "</body></html>"
        )

    @app.post("/admin/seed-strategies", response_class=HTMLResponse)
    async def seed_strategies_action(request: Request) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from app.utils.seed import seed_strategies

        try:
            created = await seed_strategies()
            status = f"Done! Created <b>{created}</b> new strategies."
        except Exception:
            logger.exception("[admin] Failed to seed strategies")
            status = "Error: failed to seed strategies. Check logs."

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>Seed Strategies</h2>"
            f"<p>{status}</p>"
            "<br><a href='/admin/beautiful-date-strategy/list'>Back to strategies</a>"
            " | <a href='/admin'>Admin home</a>"
            "</body></html>"
        )

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
            await pool.enqueue_job(
                "app.workers.notifications.send_day_before_notification", user_id, True
            )
            await pool.enqueue_job(
                "app.workers.notifications.send_week_before_notification", user_id, True
            )
            await pool.enqueue_job(
                "app.workers.notifications.send_weekly_digest_notification", user_id, True
            )
            await pool.enqueue_job(
                "app.workers.notifications.send_wish_reminders_task", user_id, True
            )
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

    @app.get("/admin/grant-premium/{user_id}", response_class=HTMLResponse)
    async def grant_premium_page(request: Request, user_id: int) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        from sqlalchemy import select

        from app.models.subscription import Subscription
        from app.models.user import User

        async with async_session_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                return HTMLResponse(
                    "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
                    f"<h2>User {user_id} not found</h2>"
                    "<br><a href='/admin'>Back</a></body></html>"
                )

            result = await session.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id, Subscription.is_active.is_(True))
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            active_sub = result.scalar_one_or_none()

        sub_info = "No active subscription"
        if active_sub:
            if active_sub.is_lifetime:
                sub_info = "Lifetime subscription (active)"
            elif active_sub.expires_at:
                sub_info = f"Active until {active_sub.expires_at.strftime('%d.%m.%Y')}"

        from html import escape

        username = escape(user.username or user.first_name or str(user_id))
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            f"<h2>Grant Premium to {username}</h2>"
            f"<p>Current: <b>{sub_info}</b></p>"
            "<form method='POST' style='margin-top:20px'>"
            "<label>Months: <input type='number' name='months' value='1' min='1' max='120' "
            "style='padding:6px;width:80px'></label>"
            "<br><br>"
            "<label><input type='checkbox' name='lifetime'> Lifetime</label>"
            "<br><br>"
            "<button type='submit' style='padding:12px 32px;font-size:16px;"
            "background:#198754;color:#fff;border:none;border-radius:6px;cursor:pointer'>"
            "Grant Premium</button>"
            "</form>"
            "<br><a href='/admin'>Cancel</a>"
            "</body></html>"
        )

    @app.post("/admin/grant-premium/{user_id}", response_class=HTMLResponse)
    async def grant_premium_action(request: Request, user_id: int) -> HTMLResponse:
        if not request.session.get("authenticated"):
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]

        form = await request.form()
        is_lifetime = form.get("lifetime") == "on"
        months = int(form.get("months", 1))

        from app.services.subscription_service import grant_subscription

        try:
            async with async_session_factory() as session:
                sub = await grant_subscription(
                    session, user_id, months=months, is_lifetime=is_lifetime, source="admin"
                )
                await session.commit()

            if sub.is_lifetime:
                status = f"Lifetime premium granted to user <b>{user_id}</b>."
            elif sub.expires_at:
                date_str = sub.expires_at.strftime("%d.%m.%Y")
                status = f"Premium granted to user <b>{user_id}</b> until <b>{date_str}</b>."
            else:
                status = f"Premium granted to user <b>{user_id}</b>."
        except Exception:
            logger.exception("[admin] Failed to grant premium to user %s", user_id)
            status = "Error: failed to grant premium. Check logs."

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>Grant Premium</h2>"
            f"<p>{status}</p>"
            f"<br><a href='/admin/user/details/{user_id}'>Back to user</a>"
            " | <a href='/admin'>Admin home</a>"
            "</body></html>"
        )

    auth_backend = AdminAuth(secret_key=settings.admin_secret_key)
    admin = Admin(
        app,
        engine,
        authentication_backend=auth_backend,
        title="Noteme Admin",
        templates_dir="app/templates/sqladmin_overrides",
    )

    from app.admin.views import (
        AILogAdmin,
        AppSettingsAdmin,
        BeautifulDateAdmin,
        BeautifulDateStrategyAdmin,
        EventAdmin,
        NotificationLogAdmin,
        PaymentAdmin,
        PersonAdmin,
        ReferralRewardAdmin,
        SubscriptionAdmin,
        SubscriptionPlanAdmin,
        UserActionLogAdmin,
        UserAdmin,
        WishAdmin,
    )

    admin.add_view(UserAdmin)
    admin.add_view(EventAdmin)
    admin.add_view(WishAdmin)
    admin.add_view(PersonAdmin)
    admin.add_view(BeautifulDateStrategyAdmin)
    admin.add_view(BeautifulDateAdmin)
    admin.add_view(SubscriptionPlanAdmin)
    admin.add_view(SubscriptionAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(ReferralRewardAdmin)
    admin.add_view(AppSettingsAdmin)
    admin.add_view(NotificationLogAdmin)
    admin.add_view(AILogAdmin)
    admin.add_view(UserActionLogAdmin)

    class DashboardMenuItem(ItemMenu):
        @property
        def type_(self) -> str:
            return "View"

        def url(self, request: Request) -> str:
            return "/admin/dashboard"

        def is_active(self, request: Request) -> bool:
            return request.url.path == "/admin/dashboard"

    class StarsMenuItem(ItemMenu):
        @property
        def type_(self) -> str:
            return "View"

        def url(self, request: Request) -> str:
            return "/admin/stars-balance"

        def is_active(self, request: Request) -> bool:
            return request.url.path == "/admin/stars-balance"

    class AICostsMenuItem(ItemMenu):
        @property
        def type_(self) -> str:
            return "View"

        def url(self, request: Request) -> str:
            return "/admin/ai-costs"

        def is_active(self, request: Request) -> bool:
            return request.url.path == "/admin/ai-costs"

    admin._menu.items.insert(0, DashboardMenuItem(name="Dashboard", icon="fa-solid fa-chart-line"))
    admin._menu.items.append(AICostsMenuItem(name="AI Costs", icon="fa-solid fa-coins"))
    admin._menu.items.append(StarsMenuItem(name="Stars Balance", icon="fa-solid fa-star"))

    app.state.admin = admin

    return admin
