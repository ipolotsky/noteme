"""AI text/voice handler — processes free-form messages through LangGraph."""

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
from app.keyboards.notes import note_view_kb
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.note import NoteCreate
from app.services.action_logger import log_user_action
from app.services.event_service import EventLimitError, create_event
from app.services.note_service import NoteLimitError, create_note

logger = logging.getLogger(__name__)

router = Router(name="ai")


def _format_user_text(text: str) -> str:
    """Clean up user input for saving as description/note text.

    - Strip whitespace
    - Capitalize first letter
    - Ensure sentence-ending punctuation
    """
    text = " ".join(text.split())  # collapse multiple spaces/newlines
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
    """Handle voice messages — transcribe then process."""
    # Check audio duration (max 1 minute)
    if message.voice.duration > 60:
        await message.answer(t("ai.audio_too_long", lang))
        return

    # Check rate limit
    if not await check_ai_rate_limit(user.id):
        await message.answer(t("ai.rate_limit", lang))
        return

    await log_user_action(user.id, "voice_message", f"duration={message.voice.duration}s")
    processing_msg = await message.answer(t("ai.processing", lang))

    try:
        # Download voice file
        logger.info("[voice] user=%s downloading file_id=%s", user.id, message.voice.file_id)
        file = await message.bot.get_file(message.voice.file_id)
        logger.info("[voice] user=%s file_path=%s", user.id, file.file_path)
        bio = await message.bot.download_file(file.file_path)
        audio_bytes = bio.read()
        logger.info("[voice] user=%s downloaded %d bytes", user.id, len(audio_bytes))

        # Transcribe — pass the real filename from Telegram
        filename = file.file_path.rsplit("/", 1)[-1] if file.file_path else "voice.oga"
        text = await transcribe_audio(audio_bytes, filename=filename, user_id=user.id)
        if not text.strip():
            await processing_msg.edit_text(t("ai.audio_empty", lang))
            return
        logger.info("[voice] user=%s transcribed: %r", user.id, text[:200])

        # Process through agent pipeline
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
    """Handle text messages — process through agent pipeline."""
    if not message.text:
        return

    # Skip commands (handled by other routers)
    if message.text.startswith("/"):
        return

    # Check rate limit
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
    """Handle the result from the agent pipeline."""
    intent = state.intent
    logger.info(
        "[handler] user=%s intent=%s title=%r date=%s note=%r error=%r",
        user.id, intent, state.event_title, state.event_date,
        state.note_text[:80] if state.note_text else "", state.error,
    )

    # Original user text — save as description (formatted)
    raw_text = state.raw_text or ""

    # If the agent wants to create an event
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
                    tag_names=state.tag_names or [],
                ),
            )
            logger.info("[handler] user=%s → event created id=%s", user.id, event.id)
            await log_user_action(user.id, "create_event", f"{event.title} ({event.event_date})")
            # Trigger beautiful dates recalculation
            from app.services.beautiful_dates.engine import recalculate_for_event
            await recalculate_for_event(session, event)

            await processing_msg.edit_text(
                t("events.created", lang, title=escape(event.title)),
                reply_markup=event_view_kb(event, lang),
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

    # If the agent wants to create a note
    if intent == "create_note" and state.note_text:
        try:
            note_text = _format_user_text(raw_text) if raw_text else state.note_text
            logger.info("[handler] user=%s → creating note", user.id)
            note = await create_note(
                session,
                user.id,
                NoteCreate(
                    text=note_text,
                    reminder_date=state.note_reminder_date,
                    tag_names=state.tag_names or [],
                ),
            )
            logger.info("[handler] user=%s → note created id=%s", user.id, note.id)
            await log_user_action(user.id, "create_note", state.note_text[:100])
            await processing_msg.edit_text(
                t("notes.created", lang),
                reply_markup=note_view_kb(note, lang),
            )
        except NoteLimitError:
            logger.warning("[handler] user=%s → note limit reached", user.id)
            await processing_msg.edit_text(
                t("notes.limit_reached", lang, max=str(user.max_notes))
            )
        except Exception:
            logger.exception("[handler] user=%s → note creation failed", user.id)
            await processing_msg.edit_text(t("errors.unknown", lang))
        return

    # View requests — redirect to appropriate screen
    if intent in ("view_events", "view_notes", "view_feed", "view_tags"):
        logger.info("[handler] user=%s → view %s", user.id, intent)
        await processing_msg.edit_text(
            state.response_text or t("menu.events", lang),
            reply_markup=main_menu_kb(lang),
        )
        return

    # Default: show response text
    logger.warning("[handler] user=%s → FALLTHROUGH intent=%s, showing response_text", user.id, intent)
    text = state.response_text or t("ai.not_understood", lang)
    await processing_msg.edit_text(text)
