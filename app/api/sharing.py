"""Public pages — landing + share beautiful date pages."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.services.beautiful_date_service import get_by_share_uuid

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    """Landing page at /."""
    bot_name = settings.bot_username or "Noteme"
    bot_url = f"https://t.me/{settings.bot_username}" if settings.bot_username else "#"

    from jinja2 import Environment, FileSystemLoader
    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    template = env.get_template("landing.html")

    html = template.render(
        bot_name=bot_name,
        bot_url=bot_url,
        base_url=settings.app_base_url,
        year=date.today().year,
    )
    return HTMLResponse(content=html)


@router.get("/share/{share_uuid}", response_class=HTMLResponse)
async def share_page(
    share_uuid: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    try:
        uid = uuid.UUID(share_uuid)
    except ValueError:
        return HTMLResponse(status_code=404, content="Not found")

    bd = await get_by_share_uuid(session, uid)
    if bd is None:
        return HTMLResponse(status_code=404, content="Not found")

    # Determine language from event owner
    from sqlalchemy import select

    from app.models.user import User
    result = await session.execute(
        select(User).where(User.id == bd.event.user_id)
    )
    user = result.scalar_one_or_none()
    lang = user.language if user else "ru"

    label = bd.label_ru if lang == "ru" else bd.label_en
    title = f"{label} | Noteme"
    bot_url = f"https://t.me/{settings.bot_username}" if settings.bot_username else "#"

    from app.i18n.loader import t
    cta = t("share.cta", lang)
    powered_by = t("share.powered_by", lang)

    from jinja2 import Environment, FileSystemLoader
    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    template = env.get_template("share.html")

    html = template.render(
        title=title,
        label=label,
        target_date=bd.target_date.strftime("%d.%m.%Y"),
        event_title=bd.event.title,
        cta=cta,
        bot_url=bot_url,
        powered_by=powered_by,
        base_url=settings.app_base_url,
    )

    return HTMLResponse(content=html)
