"""/start + onboarding handler."""

from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import OnboardingStates
from app.i18n.loader import t
from app.keyboards.callbacks import LangCb, OnboardCb
from app.keyboards.main_menu import main_menu_kb, onboarding_skip_kb
from app.keyboards.settings import language_select_kb
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.user_service import update_user

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    await state.clear()

    if user.onboarding_completed:
        await message.answer(
            t("welcome_back", lang, name=user.first_name),
            reply_markup=main_menu_kb(lang),
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


@router.message(OnboardingStates.waiting_first_event)
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
                    tag_names=result.tag_names or None,
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


@router.message(OnboardingStates.waiting_first_note)
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
        reply_markup=main_menu_kb(lang),
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
        reply_markup=main_menu_kb(lang),
    )
    await callback.answer()
