import contextlib
import logging
import uuid
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
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
from app.services.wish_service import get_wishes_by_person_names
from app.utils.date_utils import format_date, format_relative_date

router = Router(name="feed")

logger = logging.getLogger(__name__)

_FSM_KEY = "feed_message_ids"


async def _select_best_wish(wishes, label: str) -> str | None:
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
            temperature=0,
            max_tokens=10,
        )
        wishes_list = "\n".join(f"{i + 1}. {x.text[:100]}" for i, x in enumerate(wishes))
        messages = [
            {
                "role": "system",
                "content": "Select the most relevant wish for the given date milestone. Reply with ONLY the wish number.",
            },
            {
                "role": "user",
                "content": f"Milestone: {label}\n\nWishes:\n{wishes_list}\n\nBest wish number?",
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
) -> tuple[str, InlineKeyboardMarkup]:
    label = bd.label_ru if lang == "ru" else bd.label_en
    relative = format_relative_date(bd.target_date, lang)
    calendar = format_date(bd.target_date, lang)

    text = f"\U0001f52e <b>{escape(label)}</b>\n\n"
    text += f"\U0001f4c5 {calendar}\n"
    text += f"\u23f3 {relative}"

    if bd.event.people:
        person_names = [x.name for x in bd.event.people]
        wishes = await get_wishes_by_person_names(session, user_id, person_names, limit=10)
        wish = await _select_best_wish(wishes, label)
        if wish:
            text += f"\n\n{t('feed.wish', lang)}\n{escape(wish)}"

    text += f"\n\n<i>{t('feed.counter', lang, current=offset + 1, total=total)}</i>"

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

    rows.append([InlineKeyboardButton(
        text=f"\U0001f517 {t('feed.share', lang)}",
        callback_data=FeedCb(action="share", id=str(bd.id)).pack(),
    )])

    rows.append([InlineKeyboardButton(
        text=f"\u25c0 {t('menu.back', lang)}",
        callback_data=MenuCb(action="main").pack(),
    )])

    return text, InlineKeyboardMarkup(inline_keyboard=rows)


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
    text, kb = await _build_card(bd, offset, total, lang, session, user.id)
    msg = await send_to.answer(text, reply_markup=kb)
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
    text, kb = await _build_card(bd, offset, total, lang, session, user.id)
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
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


@router.callback_query(FeedCb.filter(F.action == "share"))
async def feed_share(
    callback: CallbackQuery,
    callback_data: FeedCb,
    lang: str,
    session: AsyncSession,
) -> None:
    share_uuid = await generate_share_uuid(session, uuid.UUID(callback_data.id))
    if share_uuid is None:
        await callback.answer(t("errors.not_found", lang), show_alert=True)
        return

    url = f"{settings.app_base_url}/share/{share_uuid}"
    await callback.message.answer(  # type: ignore[union-attr]
        t("feed.shared_link", lang, url=url),
    )
    await callback.answer()
