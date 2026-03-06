import logging
from html import escape

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import process_message
from app.agents.rate_limit import check_ai_rate_limit
from app.agents.whisper import transcribe_audio
from app.i18n.loader import t
from app.keyboards.events import event_view_kb
from app.keyboards.main_menu import main_menu_kb
from app.keyboards.wishes import wish_view_kb
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.wish import WishCreate
from app.services.action_logger import log_user_action
from app.services.event_service import EventLimitError, create_event
from app.services.wish_service import WishLimitError, create_wish

logger = logging.getLogger(__name__)

router = Router(name="ai")


def _format_user_text(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?…":
        text += "."
    return text


@router.message(F.voice)
async def handle_voice(
    message: Message,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    if message.voice.duration > 60:
        await message.answer(t("ai.audio_too_long", lang))
        return

    if not await check_ai_rate_limit(user.id):
        await message.answer(t("ai.rate_limit", lang))
        return

    await log_user_action(user.id, "voice_message", f"duration={message.voice.duration}s")
    processing_msg = await message.answer(t("ai.processing", lang))

    try:
        logger.info("[voice] user=%s downloading file_id=%s", user.id, message.voice.file_id)
        file = await message.bot.get_file(message.voice.file_id)
        logger.info("[voice] user=%s file_path=%s", user.id, file.file_path)
        bio = await message.bot.download_file(file.file_path)
        audio_bytes = bio.read()
        logger.info("[voice] user=%s downloaded %d bytes", user.id, len(audio_bytes))

        filename = file.file_path.rsplit("/", 1)[-1] if file.file_path else "voice.oga"
        text = await transcribe_audio(audio_bytes, filename=filename, user_id=user.id)
        if not text.strip():
            await processing_msg.edit_text(t("ai.audio_empty", lang))
            return
        logger.info("[voice] user=%s transcribed: %r", user.id, text[:200])

        state = await process_message(
            text=text,
            user_id=user.id,
            user_language=lang,
            is_voice=True,
        )

        await _handle_agent_result(message, processing_msg, state, user, lang, session)

    except Exception:
        logger.exception("Voice processing failed for user %s", user.id)
        await processing_msg.edit_text(t("errors.unknown", lang))


@router.message(F.text)
async def handle_text(
    message: Message,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    if not message.text:
        return

    if message.text.startswith("/"):
        return

    if not await check_ai_rate_limit(user.id):
        await message.answer(t("ai.rate_limit", lang))
        return

    await log_user_action(user.id, "text_message", message.text[:200])
    processing_msg = await message.answer(t("ai.processing", lang))

    try:
        state = await process_message(
            text=message.text,
            user_id=user.id,
            user_language=lang,
        )

        await _handle_agent_result(message, processing_msg, state, user, lang, session)

    except Exception:
        logger.exception("Text processing failed for user %s", user.id)
        await processing_msg.edit_text(t("errors.unknown", lang))


async def _handle_agent_result(
    original: Message,
    processing_msg: Message,
    state,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    intent = state.intent
    logger.info(
        "[handler] user=%s intent=%s title=%r date=%s wish=%r error=%r",
        user.id, intent, state.event_title, state.event_date,
        state.wish_text[:80] if state.wish_text else "", state.error,
    )

    raw_text = state.raw_text or ""

    person_names = (state.person_names or [])[:2]
    if not person_names:
        person_names = ["Личное" if lang == "ru" else "Personal"]

    if intent == "create_event" and state.event_title and state.event_date:
        try:
            description = _format_user_text(raw_text) if raw_text else (state.event_description or None)
            logger.info("[handler] user=%s → creating event %r on %s", user.id, state.event_title, state.event_date)
            event = await create_event(
                session,
                user.id,
                EventCreate(
                    title=state.event_title,
                    event_date=state.event_date,
                    description=description,
                    person_names=person_names,
                ),
            )
            logger.info("[handler] user=%s → event created id=%s", user.id, event.id)
            await log_user_action(user.id, "create_event", f"{event.title} ({event.event_date})")
            from app.services.beautiful_dates.engine import recalculate_for_event
            await recalculate_for_event(session, event)

            from app.handlers.events import _build_event_card
            card, related_count, person_counts = await _build_event_card(event, user, lang, session)
            await processing_msg.edit_text(
                card,
                reply_markup=event_view_kb(
                    event, lang,
                    related_wishes_count=related_count,
                    person_event_counts=person_counts,
                ),
            )
        except EventLimitError:
            logger.warning("[handler] user=%s → event limit reached", user.id)
            await processing_msg.edit_text(
                t("events.limit_reached", lang, max=str(user.max_events))
            )
        except Exception:
            logger.exception("[handler] user=%s → event creation failed", user.id)
            await processing_msg.edit_text(t("errors.unknown", lang))
        return

    if intent == "create_wish" and state.wish_text:
        try:
            wish_text = _format_user_text(raw_text) if raw_text else state.wish_text
            logger.info("[handler] user=%s → creating wish", user.id)
            wish = await create_wish(
                session,
                user.id,
                WishCreate(
                    text=wish_text,
                    reminder_date=state.wish_reminder_date,
                    person_names=person_names,
                ),
            )
            logger.info("[handler] user=%s → wish created id=%s", user.id, wish.id)
            await log_user_action(user.id, "create_wish", state.wish_text[:100])
            people_str = ", ".join(escape(x.name) for x in wish.people) if wish.people else t("wishes.no_people", lang)
            card = (
                f"<b>{t('wishes.view_title', lang)}</b>\n\n"
                f"{escape(wish.text)}\n\n"
                f"{t('wishes.people_label', lang, people=people_str)}"
            )
            if wish.reminder_date:
                card += f"\n{t('wishes.reminder_set', lang, date=wish.reminder_date.strftime('%d.%m.%Y'))}"
            await processing_msg.edit_text(card, reply_markup=wish_view_kb(wish, lang))
        except WishLimitError:
            logger.warning("[handler] user=%s → wish limit reached", user.id)
            await processing_msg.edit_text(
                t("wishes.limit_reached", lang, max=str(user.max_wishes))
            )
        except Exception:
            logger.exception("[handler] user=%s → wish creation failed", user.id)
            await processing_msg.edit_text(t("errors.unknown", lang))
        return

    if intent in ("view_events", "view_wishes", "view_feed", "view_people"):
        logger.info("[handler] user=%s → view %s", user.id, intent)
        await processing_msg.edit_text(
            state.response_text or t("menu.events", lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    logger.warning("[handler] user=%s → FALLTHROUGH intent=%s, showing response_text", user.id, intent)
    text = state.response_text or t("ai.not_understood", lang)
    await processing_msg.edit_text(text)
