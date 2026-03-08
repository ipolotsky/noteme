import asyncio
import contextlib
import logging
import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.i18n.loader import t
from app.keyboards.callbacks import EventCb, FeedCb, MenuCb
from app.models.beautiful_date import BeautifulDate
from app.models.event import Event
from app.models.user import User
from app.services.beautiful_date_service import (
    count_user_feed,
    generate_share_uuid,
    get_user_feed,
)
from app.services.share_image import generate_share_image
from app.services.wish_service import get_wishes_by_person_names
from app.utils.date_utils import format_date, format_relative_date

router = Router(name="feed")

logger = logging.getLogger(__name__)

_FSM_KEY = "feed_message_ids"


async def _select_best_wish(
    wishes,
    label: str,
    event_title: str = "",
    target_date_str: str = "",
    relative_date_str: str = "",
) -> str | None:
    if not wishes:
        return None
    if len(wishes) == 1:
        return wishes[0].text
    if not settings.openai_api_key:
        return wishes[0].text
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=10,
        )
        wishes_list = "\n".join(f"{i + 1}. {x.text[:200]}" for i, x in enumerate(wishes))
        context_parts = [f"Milestone: {label}"]
        if event_title:
            context_parts.append(f"Event: {event_title}")
        if target_date_str:
            context_parts.append(f"Date: {target_date_str}")
        if relative_date_str:
            context_parts.append(f"When: {relative_date_str}")
        context = "\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": (
                    "You help pick the most fitting wish/gift idea for a date milestone. "
                    "Consider relevance to the event, timing, and how well the wish matches the occasion. "
                    "Reply with ONLY the wish number."
                ),
            },
            {
                "role": "user",
                "content": f"{context}\n\nWishes:\n{wishes_list}\n\nBest wish number?",
            },
        ]
        response = await llm.ainvoke(messages)
        idx = int(str(response.content).strip()) - 1
        if 0 <= idx < len(wishes):
            return wishes[idx].text
    except Exception:
        logger.debug("wish selector fallback to first wish")
    return wishes[0].text


async def _build_card(
    bd: BeautifulDate,
    offset: int,
    total: int,
    lang: str,
    session: AsyncSession,
    user_id: int,
) -> tuple[bytes, str, InlineKeyboardMarkup]:
    label = bd.label_ru if lang == "ru" else bd.label_en
    relative = format_relative_date(bd.target_date, lang)
    calendar = format_date(bd.target_date, lang)
    person_names = [x.name for x in bd.event.people] if bd.event.people else []

    image_bytes = await asyncio.to_thread(
        generate_share_image,
        label=label,
        event_title=bd.event.title,
        target_date_formatted=calendar,
        relative_date=relative,
    )

    caption = ""
    if bd.event.people:
        wishes = await get_wishes_by_person_names(session, user_id, person_names, limit=10)
        wish = await _select_best_wish(
            wishes, label,
            event_title=bd.event.title,
            target_date_str=calendar,
            relative_date_str=relative,
        )
        if wish:
            caption = f"{t('feed.wish', lang)}\n{escape(wish)}"

    rows: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(
            text=f"\u25c0 {t('feed.prev', lang)}",
            callback_data=FeedCb(action="card", page=offset - 1).pack(),
        ))
    if offset < total - 1:
        nav_row.append(InlineKeyboardButton(
            text=f"{t('feed.next', lang)} \u25b6",
            callback_data=FeedCb(action="card", page=offset + 1).pack(),
        ))
    if nav_row:
        rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(
            text=f"\U0001f4c5 {t('feed.to_event', lang)}",
            callback_data=EventCb(action="view_new", id=str(bd.event_id)).pack(),
        ),
        InlineKeyboardButton(
            text=f"\U0001f4cb {t('feed.all_wishes', lang)}",
            callback_data=FeedCb(action="wishes", id=str(bd.id)).pack(),
        ),
    ])

    share_uuid = await generate_share_uuid(session, bd.id)
    if share_uuid:
        mini_app_url = f"{settings.app_base_url}/mini-app/card/{share_uuid}"
        rows.append([InlineKeyboardButton(
            text=f"\U0001f517 {t('feed.share', lang)}",
            web_app=WebAppInfo(url=mini_app_url),
        )])

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return image_bytes, caption, InlineKeyboardMarkup(inline_keyboard=rows)


async def _delete_previous_feed(chat_id: int, state: FSMContext, bot) -> None:
    data = await state.get_data()
    msg_ids = data.get(_FSM_KEY, [])
    for mid in msg_ids:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id, mid)
    await state.update_data(**{_FSM_KEY: []})


async def _show_card_new(
    send_to: Message,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    offset: int = 0,
) -> bool:
    total = await count_user_feed(session, user.id)
    if total == 0:
        return False

    offset = max(0, min(offset, total - 1))
    items = await get_user_feed(session, user.id, offset=offset, limit=1)
    if not items:
        return False

    bd = items[0]
    image_bytes, caption, kb = await _build_card(bd, offset, total, lang, session, user.id)
    photo = BufferedInputFile(image_bytes, filename="card.png")
    msg = await send_to.answer_photo(photo=photo, caption=caption, reply_markup=kb)
    await state.update_data(**{_FSM_KEY: [msg.message_id]})
    return True


async def show_feed_list(
    callback: CallbackQuery,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    page: int = 0,
) -> None:
    await _delete_previous_feed(callback.message.chat.id, state, callback.bot)  # type: ignore[union-attr]

    sent = await _show_card_new(callback.message, user, lang, session, state, offset=page)  # type: ignore[arg-type]
    if not sent:
        from app.keyboards.main_menu import main_menu_kb

        await callback.message.edit_text(  # type: ignore[union-attr]
            t("feed.empty", lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    with contextlib.suppress(Exception):
        await callback.message.delete()  # type: ignore[union-attr]


async def send_feed_messages(
    message: Message,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
    page: int = 0,
) -> None:
    from app.keyboards.main_menu import main_menu_kb

    await _delete_previous_feed(message.chat.id, state, message.bot)

    sent = await _show_card_new(message, user, lang, session, state, offset=page)
    if not sent:
        await message.answer(t("feed.empty", lang), reply_markup=main_menu_kb(lang))


@router.callback_query(FeedCb.filter(F.action == "list"))
async def feed_list(
    callback: CallbackQuery,
    callback_data: FeedCb,
    user: User,
    lang: str,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await show_feed_list(callback, user, lang, session, state, page=callback_data.page)
    await callback.answer()


@router.callback_query(FeedCb.filter(F.action == "card"))
async def feed_card(
    callback: CallbackQuery,
    callback_data: FeedCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    total = await count_user_feed(session, user.id)
    if total == 0:
        await callback.answer(t("feed.empty", lang), show_alert=True)
        return

    offset = max(0, min(callback_data.page, total - 1))
    items = await get_user_feed(session, user.id, offset=offset, limit=1)
    if not items:
        await callback.answer()
        return

    bd = items[0]
    image_bytes, caption, kb = await _build_card(bd, offset, total, lang, session, user.id)
    photo = BufferedInputFile(image_bytes, filename="card.png")
    await callback.message.edit_media(  # type: ignore[union-attr]
        InputMediaPhoto(media=photo, caption=caption),
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(FeedCb.filter(F.action == "wishes"))
async def feed_wishes(
    callback: CallbackQuery,
    callback_data: FeedCb,
    lang: str,
    session: AsyncSession,
) -> None:
    bd_id = uuid.UUID(callback_data.id)
    result = await session.execute(
        select(BeautifulDate)
        .options(selectinload(BeautifulDate.event).selectinload(Event.people))
        .where(BeautifulDate.id == bd_id)
    )
    bd = result.scalar_one_or_none()

    if bd is None or not bd.event.people:
        await callback.answer(t("feed.no_wishes", lang), show_alert=True)
        return

    person_names = [x.name for x in bd.event.people]
    wishes = await get_wishes_by_person_names(session, bd.event.user_id, person_names, limit=20)

    if not wishes:
        await callback.answer(t("feed.no_wishes", lang), show_alert=True)
        return

    label = bd.label_ru if lang == "ru" else bd.label_en
    text = f"\U0001f4cb <b>{escape(label)}</b>\n\n"
    for x in wishes:
        text += f"- {escape(x.text[:120])}\n"

    await callback.message.answer(text)  # type: ignore[union-attr]
    await callback.answer()


