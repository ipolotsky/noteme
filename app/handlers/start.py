import logging
from datetime import date, timedelta
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.states import OnboardingStates
from app.i18n.loader import t
from app.keyboards.callbacks import LangCb, OnboardCb
from app.keyboards.main_menu import (
    onboarding_event_kb,
    onboarding_example_kb,
    onboarding_intro_kb,
    onboarding_skip_kb,
    persistent_menu_kb,
)
from app.keyboards.settings import language_select_kb
from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.action_logger import log_user_action
from app.services.user_service import update_user
from app.utils.bot_utils import transcribe_voice

logger = logging.getLogger(__name__)

router = Router(name="start")

ONBOARDING_GIF = Path(__file__).resolve().parent.parent / "assets" / "onboarding.gif"

MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def _format_date(d: date, lang: str) -> str:
    if lang == "ru":
        return f"{d.day} {MONTHS_RU[d.month]} {d.year}"
    return d.strftime("%B %d, %Y")


def _date_777_ago() -> date:
    return date.today() - timedelta(days=777)


def _date_example() -> date:
    return date.today() - relativedelta(years=3, months=3, days=4)


def _build_step2_text(lang: str, person_names: list[str]) -> str:
    real_names = [n for n in person_names if n not in ("Личное", "Personal")]
    if real_names:
        return t("onboarding.step2_with_person", lang, name=real_names[0])
    return t("onboarding.step2_personal", lang)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
    command: CommandObject | None = None,
) -> None:
    await state.clear()
    await log_user_action(user.id, "start")

    if command and command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args[4:])
            if referrer_id != user.id and user.referred_by is None:
                from app.services.user_service import get_user

                referrer = await get_user(session, referrer_id)
                if referrer is not None:
                    user.referred_by = referrer_id
                    await session.flush()
                    from app.services.referral_service import process_referral

                    reward_months = await process_referral(session, referrer_id, user.id)
                    if reward_months is not None:
                        try:
                            referrer_lang = referrer.language or "ru"
                            await message.bot.send_message(
                                referrer_id,
                                t("subscription.referral_bonus", referrer_lang, months=reward_months),
                            )
                        except Exception:
                            logger.warning("Failed to send referral notification to %d", referrer_id)
        except ValueError:
            logger.warning("Invalid referral args: %s", command.args)
        except Exception:
            logger.exception("Referral processing failed for args: %s", command.args)

    if user.onboarding_completed:
        await message.answer(
            t("welcome_back", lang, name=user.first_name),
            reply_markup=persistent_menu_kb(lang),
        )
        return

    await message.answer_animation(animation=FSInputFile(ONBOARDING_GIF))
    await message.answer(
        t("welcome", lang, name=user.first_name),
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
        t("language_set", lang),
    )
    await callback.message.answer(  # type: ignore[union-attr]
        t("onboarding.intro", lang),
        reply_markup=onboarding_intro_kb(lang),
        parse_mode="HTML",
    )
    await state.set_state(OnboardingStates.waiting_intro_response)
    await state.update_data(lang=lang)
    await callback.answer()


@router.callback_query(
    OnboardingStates.waiting_intro_response,
    OnboardCb.filter(F.action == "dont_get_it"),
)
async def onboarding_intro_button(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    await _send_example(callback.message, state, lang)  # type: ignore[arg-type]
    await callback.answer()


@router.message(OnboardingStates.waiting_intro_response, F.text)
async def onboarding_intro_text(
    message: Message,
    state: FSMContext,
    user: User,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)
    await _send_example(message, state, lang)


async def _send_example(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    date_777 = _format_date(_date_777_ago(), lang)
    await message.answer(
        t("onboarding.example", lang, date_777=date_777),
        reply_markup=onboarding_example_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_example_response)


@router.callback_query(
    OnboardingStates.waiting_example_response,
    OnboardCb.filter(F.action == "more_example"),
)
async def onboarding_more_example(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    date_ex = _format_date(_date_example(), lang)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.step1_more", lang, date_example=date_ex),
        reply_markup=onboarding_event_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_event)
    await callback.answer()


@router.callback_query(
    OnboardingStates.waiting_example_response,
    OnboardCb.filter(F.action == "got_it"),
)
async def onboarding_got_it(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    date_ex = _format_date(_date_example(), lang)
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.step1_got_it", lang, date_example=date_ex),
        reply_markup=onboarding_event_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_event)
    await callback.answer()


async def _handle_event_created(
    message: Message,
    state: FSMContext,
    lang: str,
    person_names: list[str],
) -> None:
    step2_text = _build_step2_text(lang, person_names)
    await message.answer(step2_text, reply_markup=onboarding_skip_kb(lang))
    await state.set_state(OnboardingStates.waiting_first_wish)


@router.message(OnboardingStates.waiting_first_event, F.text)
async def onboarding_first_event_text(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    processing_msg = await message.answer(t("ai.processing", lang))

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
            person_names = result.person_names or []
            event = await create_event(
                session,
                user.id,
                EventCreate(
                    title=result.event_title,
                    event_date=result.event_date,
                    person_names=person_names,
                ),
            )
            from app.services.beautiful_dates.engine import recalculate_for_event

            await recalculate_for_event(session, event)
            await processing_msg.edit_text(t("events.created", lang, title=escape(event.title)))
            await state.update_data(event_created=True)
            await log_user_action(user.id, "onboarding_create_event", event.title)
        else:
            await processing_msg.edit_text(
                t("ai.not_understood", lang),
                reply_markup=onboarding_event_kb(lang),
            )
            return
    except Exception:
        await processing_msg.edit_text(
            t("ai.not_understood", lang),
            reply_markup=onboarding_event_kb(lang),
        )
        return

    await _handle_event_created(message, state, lang, person_names)


@router.message(OnboardingStates.waiting_first_event, F.voice)
async def onboarding_first_event_voice(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    processing_msg = await message.answer(t("ai.processing", lang))

    text = await transcribe_voice(message, lang, user_id=user.id)
    if text is None:
        await processing_msg.delete()
        return

    try:
        from app.agents.graph import process_message
        from app.schemas.event import EventCreate
        from app.services.event_service import create_event

        result = await process_message(
            text=text, user_id=user.id, user_language=lang, is_voice=True
        )

        if result.intent == "create_event" and result.event_title and result.event_date:
            person_names = result.person_names or []
            event = await create_event(
                session,
                user.id,
                EventCreate(
                    title=result.event_title,
                    event_date=result.event_date,
                    person_names=person_names,
                ),
            )
            from app.services.beautiful_dates.engine import recalculate_for_event

            await recalculate_for_event(session, event)
            await processing_msg.edit_text(t("events.created", lang, title=escape(event.title)))
            await state.update_data(event_created=True)
            await log_user_action(user.id, "onboarding_create_event_voice", event.title)
        else:
            await processing_msg.edit_text(
                t("ai.not_understood", lang), reply_markup=onboarding_event_kb(lang)
            )
            return
    except Exception:
        logger.exception("Onboarding voice event failed for user %s", user.id)
        await processing_msg.edit_text(
            t("ai.not_understood", lang), reply_markup=onboarding_event_kb(lang)
        )
        return

    await _handle_event_created(message, state, lang, person_names)


@router.callback_query(
    OnboardingStates.waiting_first_event,
    OnboardCb.filter(F.action == "quick_event"),
)
async def onboarding_quick_event(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    from app.schemas.event import EventCreate
    from app.services.event_service import create_event

    title = t("onboarding.quick_event", lang)
    person_names = ["Личное" if lang == "ru" else "Personal"]
    event = await create_event(
        session,
        user.id,
        EventCreate(title=title, event_date=date.today(), person_names=person_names),
    )
    from app.services.beautiful_dates.engine import recalculate_for_event

    await recalculate_for_event(session, event)

    await callback.message.edit_text(  # type: ignore[union-attr]
        t("events.created", lang, title=escape(event.title)),
    )
    await state.update_data(event_created=True)
    await log_user_action(user.id, "onboarding_quick_event")

    step2_text = _build_step2_text(lang, person_names)
    await callback.message.answer(  # type: ignore[union-attr]
        step2_text,
        reply_markup=onboarding_skip_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_wish)
    await callback.answer()


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

    from app.schemas.event import EventCreate
    from app.services.event_service import create_event

    title = t("onboarding.quick_event", lang)
    person_names = ["Личное" if lang == "ru" else "Personal"]
    event = await create_event(
        session,
        user.id,
        EventCreate(title=title, event_date=date.today(), person_names=person_names),
    )
    from app.services.beautiful_dates.engine import recalculate_for_event

    await recalculate_for_event(session, event)
    await state.update_data(event_created=True)

    await log_user_action(user.id, "onboarding_skip_event")
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.skipped", lang),
    )

    step2_text = _build_step2_text(lang, person_names)
    await callback.message.answer(  # type: ignore[union-attr]
        step2_text,
        reply_markup=onboarding_skip_kb(lang),
    )
    await state.set_state(OnboardingStates.waiting_first_wish)
    await callback.answer()


async def _finish_onboarding(
    message: Message,
    state: FSMContext,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    event_created = data.get("event_created", False)

    await update_user(session, user.id, UserUpdate(onboarding_completed=True))
    await log_user_action(user.id, "onboarding_completed")
    await state.clear()
    await message.answer(
        t("onboarding.step3", lang),
        reply_markup=persistent_menu_kb(lang),
    )

    if event_created:
        from app.handlers.feed import send_feed_messages

        await send_feed_messages(message, user, lang, session, state)


async def _create_wish_via_ai(
    text: str,
    user: User,
    lang: str,
    session: AsyncSession,
) -> bool:
    from app.agents.graph import process_message
    from app.schemas.wish import WishCreate
    from app.services.wish_service import create_wish

    result = await process_message(text=text, user_id=user.id, user_language=lang)

    person_names = (result.person_names or [])[:2]
    if not person_names:
        person_names = ["Личное" if lang == "ru" else "Personal"]

    wish_text = " ".join(text.split())
    if wish_text:
        wish_text = wish_text[0].upper() + wish_text[1:]
        if wish_text[-1] not in ".!?":
            wish_text += "."

    await create_wish(
        session,
        user.id,
        WishCreate(
            text=wish_text,
            person_names=person_names,
        ),
    )
    return True


@router.message(OnboardingStates.waiting_first_wish, F.text)
async def onboarding_first_wish_text(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    processing_msg = await message.answer(t("ai.processing", lang))

    try:
        await _create_wish_via_ai(message.text or "", user, lang, session)
        await processing_msg.edit_text(t("wishes.created", lang))
        await log_user_action(user.id, "onboarding_create_wish")
    except Exception:
        await processing_msg.edit_text(
            t("ai.not_understood", lang),
            reply_markup=onboarding_skip_kb(lang),
        )
        return

    await _finish_onboarding(message, state, user, lang, session)


@router.message(OnboardingStates.waiting_first_wish, F.voice)
async def onboarding_first_wish_voice(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    processing_msg = await message.answer(t("ai.processing", lang))

    text = await transcribe_voice(message, lang, user_id=user.id)
    if text is None:
        await processing_msg.delete()
        return

    try:
        await _create_wish_via_ai(text, user, lang, session)
        await processing_msg.edit_text(t("wishes.created", lang))
        await log_user_action(user.id, "onboarding_create_wish_voice")
    except Exception:
        logger.exception("Onboarding voice wish failed for user %s", user.id)
        await processing_msg.edit_text(
            t("ai.not_understood", lang), reply_markup=onboarding_skip_kb(lang)
        )
        return

    await _finish_onboarding(message, state, user, lang, session)


@router.callback_query(
    OnboardingStates.waiting_first_wish,
    OnboardCb.filter(F.action == "skip"),
)
async def onboarding_skip_wish(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    lang = data.get("lang", user.language)

    await log_user_action(user.id, "onboarding_skip_wish")
    await callback.message.edit_text(  # type: ignore[union-attr]
        t("onboarding.step2_personal", lang).split("\n")[0] + " \u2714",
    )
    await _finish_onboarding(
        callback.message,
        state,
        user,
        lang,
        session,  # type: ignore[arg-type]
    )
    await callback.answer()
