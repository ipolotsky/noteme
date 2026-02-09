"""/start + onboarding handler."""

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import OnboardingStates
from app.i18n.loader import t
from app.keyboards.callbacks import LangCb, OnboardCb
from app.keyboards.main_menu import onboarding_skip_kb, persistent_menu_kb
from app.keyboards.settings import language_select_kb
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.action_logger import log_user_action
from app.services.user_service import update_user

logger = logging.getLogger(__name__)

router = Router(name="start")


async def _transcribe_voice(message: Message, lang: str) -> str | None:
    """Transcribe a voice message. Returns text or None on failure."""
    from app.agents.whisper import transcribe_audio

    if message.voice.duration > 60:  # type: ignore[union-attr]
        await message.answer(t("ai.audio_too_long", lang))
        return None

    try:
        file = await message.bot.get_file(message.voice.file_id)  # type: ignore[union-attr]
        bio = await message.bot.download_file(file.file_path)  # type: ignore[union-attr]
        audio_bytes = bio.read()  # type: ignore[union-attr]
        filename = file.file_path.rsplit("/", 1)[-1] if file.file_path else "voice.oga"
        text = await transcribe_audio(audio_bytes, filename=filename, user_id=0)
        if not text.strip():
            await message.answer(t("ai.audio_empty", lang))
            return None
        return text
    except Exception:
        logger.exception("Voice transcription failed")
        await message.answer(t("errors.unknown", lang))
        return None


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()
    await log_user_action(user.id, "start")

    if user.onboarding_completed:
        # Send persistent reply keyboard first, then inline menu
        await message.answer(
            t("welcome_back", lang, name=user.first_name),
            reply_markup=persistent_menu_kb(lang),
        )
        return

    # Start onboarding: language selection
    await message.answer(
        t("welcome", lang, name=user.first_name)
        + "\n\n"
        + t("choose_language", lang),
        reply_markup=language_select_kb(),
    )
    await state.set_state(OnboardingStates.waiting_language)


@router.callback_query(
    OnboardingStates.waiting_language,
    LangCb.filter(),
)
async def onboarding_language(
    callback: CallbackQuery,
    callback_data: LangCb,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    lang = callback_data.code
    await update_user(session, user.id, UserUpdate(language=lang))
    await log_user_action(user.id, "set_language", lang)

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("language_set", lang)
        + "\n\n"
        + t("onboarding.step1", lang),
        reply_markup=onboarding_skip_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_event)
    await state.update_data(lang=lang)
    await callback.answer()


# --- Step 1: first event (text or skip) ---


@router.message(OnboardingStates.waiting_first_event, F.text)
async def onboarding_first_event_text(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """User typed text during onboarding step 1 — create event via AI, then advance."""
    data = await state.get_data()
    lang = data.get("lang", user.language)

    try:
        from app.agents.graph import process_message
        from app.schemas.event import EventCreate
        from app.services.event_service import create_event

        result = await process_message(
            text=message.text or "",
            user_id=user.id,
            user_language=lang,
        )

        if result.intent == "create_event" and result.event_title and result.event_date:
            event = await create_event(
                session, user.id,
                EventCreate(
                    title=result.event_title,
                    event_date=result.event_date,
                    tag_names=result.tag_names or [],
                ),
            )
            from app.services.beautiful_dates.engine import recalculate_for_event
            await recalculate_for_event(session, event)
            await message.answer(t("events.created", lang, title=escape(event.title)))
        else:
            await message.answer(
                t("ai.not_understood", lang),
                reply_markup=onboarding_skip_kb(lang),
            )
            return  # Stay in state, let user try again or skip
    except Exception:
        await message.answer(
            t("ai.not_understood", lang),
            reply_markup=onboarding_skip_kb(lang),
        )
        return

    # Advance to step 2
    await message.answer(
        t("onboarding.step2", lang),
        reply_markup=onboarding_skip_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_note)


@router.message(OnboardingStates.waiting_first_event, F.voice)
async def onboarding_first_event_voice(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """User sent voice during onboarding step 1 — transcribe, create event, advance."""
    data = await state.get_data()
    lang = data.get("lang", user.language)

    text = await _transcribe_voice(message, lang)
    if text is None:
        return

    try:
        from app.agents.graph import process_message
        from app.schemas.event import EventCreate
        from app.services.event_service import create_event

        result = await process_message(text=text, user_id=user.id, user_language=lang, is_voice=True)

        if result.intent == "create_event" and result.event_title and result.event_date:
            event = await create_event(
                session, user.id,
                EventCreate(
                    title=result.event_title,
                    event_date=result.event_date,
                    tag_names=result.tag_names or [],
                ),
            )
            from app.services.beautiful_dates.engine import recalculate_for_event
            await recalculate_for_event(session, event)
            await message.answer(t("events.created", lang, title=escape(event.title)))
        else:
            await message.answer(t("ai.not_understood", lang), reply_markup=onboarding_skip_kb(lang))
            return
    except Exception:
        logger.exception("Onboarding voice event failed for user %s", user.id)
        await message.answer(t("ai.not_understood", lang), reply_markup=onboarding_skip_kb(lang))
        return

    await message.answer(t("onboarding.step2", lang), reply_markup=onboarding_skip_kb(lang))
    await state.set_state(OnboardingStates.waiting_first_note)


@router.callback_query(
    OnboardingStates.waiting_first_event,
    OnboardCb.filter(F.action == "skip"),
)
async def onboarding_skip_event(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.step2", lang),
        reply_markup=onboarding_skip_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_note)
    await callback.answer()


# --- Step 2: first note (text or skip) ---


@router.message(OnboardingStates.waiting_first_note, F.text)
async def onboarding_first_note_text(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """User typed text during onboarding step 2 — create note, then finish."""
    data = await state.get_data()
    lang = data.get("lang", user.language)

    try:
        from app.schemas.note import NoteCreate
        from app.services.note_service import create_note

        await create_note(
            session, user.id,
            NoteCreate(text=message.text or ""),
        )
        await message.answer(t("notes.created", lang))
    except Exception:
        await message.answer(
            t("ai.not_understood", lang),
            reply_markup=onboarding_skip_kb(lang),
        )
        return

    # Finish onboarding
    await update_user(session, user.id, UserUpdate(onboarding_completed=True))
    await state.clear()
    await message.answer(t("onboarding.step3", lang))
    await message.answer(
        t("welcome_back", lang, name=user.first_name),
        reply_markup=persistent_menu_kb(lang),
    )


@router.message(OnboardingStates.waiting_first_note, F.voice)
async def onboarding_first_note_voice(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """User sent voice during onboarding step 2 — transcribe, create note, finish."""
    data = await state.get_data()
    lang = data.get("lang", user.language)

    text = await _transcribe_voice(message, lang)
    if text is None:
        return

    try:
        from app.schemas.note import NoteCreate
        from app.services.note_service import create_note

        await create_note(session, user.id, NoteCreate(text=text))
        await message.answer(t("notes.created", lang))
    except Exception:
        logger.exception("Onboarding voice note failed for user %s", user.id)
        await message.answer(t("ai.not_understood", lang), reply_markup=onboarding_skip_kb(lang))
        return

    await update_user(session, user.id, UserUpdate(onboarding_completed=True))
    await state.clear()
    await message.answer(t("onboarding.step3", lang))
    await message.answer(
        t("welcome_back", lang, name=user.first_name),
        reply_markup=persistent_menu_kb(lang),
    )


@router.callback_query(
    OnboardingStates.waiting_first_note,
    OnboardCb.filter(F.action == "skip"),
)
async def onboarding_skip_note(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    await update_user(session, user.id, UserUpdate(onboarding_completed=True))
    await state.clear()

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.step3", lang),
    )
    await callback.message.answer(  # type: ignore[union-attr]
        t("welcome_back", lang, name=user.first_name),
        reply_markup=persistent_menu_kb(lang),
    )
    await callback.answer()
