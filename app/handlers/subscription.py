"""Subscription handlers — /subscribe, payment flow, referral link."""

import logging
import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.i18n.loader import t
from app.keyboards.callbacks import SubscribeCb
from app.keyboards.subscription import subscription_plans_kb
from app.models.payment import Payment
from app.models.user import User
from app.services.action_logger import log_user_action
from app.services.subscription_service import (
    activate_subscription,
    get_active_subscription,
    get_subscription_plans,
)

logger = logging.getLogger(__name__)

router = Router(name="subscription")


async def _show_plans(target: Message, user: User, lang: str, session: AsyncSession) -> None:
    subscription = await get_active_subscription(session, user.id)
    if subscription is not None:
        if subscription.is_lifetime:
            await target.answer(t("subscription.current_lifetime", lang))
            return
        if subscription.expires_at:
            date_str = subscription.expires_at.strftime("%d.%m.%Y")
            await target.answer(t("subscription.current_expires", lang, date=date_str))
            return

    plans = await get_subscription_plans(session)
    if not plans:
        await target.answer(t("subscription.no_subscription", lang))
        return

    await target.answer(
        t("subscription.choose_plan", lang),
        reply_markup=subscription_plans_kb(plans, lang),
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, user: User, lang: str, session: AsyncSession) -> None:
    await log_user_action(user.id, "subscribe_view")
    await _show_plans(message, user, lang, session)


@router.callback_query(SubscribeCb.filter(F.action == "plans"))
async def subscribe_plans(
    callback: CallbackQuery, user: User, lang: str, session: AsyncSession
) -> None:
    await _show_plans(callback.message, user, lang, session)  # type: ignore[arg-type]
    await callback.answer()


@router.callback_query(SubscribeCb.filter(F.action == "buy"))
async def subscribe_buy(
    callback: CallbackQuery,
    callback_data: SubscribeCb,
    user: User,
    lang: str,
    session: AsyncSession,
) -> None:
    from app.models.subscription_plan import SubscriptionPlan

    plan = await session.get(SubscriptionPlan, uuid.UUID(callback_data.id))
    if plan is None or not plan.is_active:
        await callback.answer("Plan not available", show_alert=True)
        return

    name = plan.name_ru if lang == "ru" else plan.name_en
    description = (plan.description_ru if lang == "ru" else plan.description_en) or name

    await callback.message.answer_invoice(  # type: ignore[union-attr]
        title=name,
        description=description,
        payload=f"sub:{plan.id}",
        currency="XTR",
        prices=[LabeledPrice(label=name, amount=plan.price_stars)],
        provider_token="",
    )
    await callback.answer()
    await log_user_action(user.id, "subscribe_buy_intent", str(plan.id))


@router.callback_query(SubscribeCb.filter(F.action == "referral"))
async def subscribe_referral(
    callback: CallbackQuery, user: User, lang: str, session: AsyncSession
) -> None:
    from app.services.app_settings_service import get_int_setting
    from app.services.referral_service import get_referral_link, get_referral_stats

    months = await get_int_setting(session, "referral_reward_months", 1)
    link = get_referral_link(settings.bot_username, user.id)
    stats = await get_referral_stats(session, user.id)

    text = t("subscription.referral_link", lang, months=str(months), link=link)
    text += "\n\n" + t("subscription.referral_stats", lang, count=str(stats["referral_count"]))

    await callback.message.answer(text)  # type: ignore[union-attr]
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession) -> None:
    payload = query.invoice_payload
    if not payload.startswith("sub:"):
        await query.answer(ok=False, error_message="Invalid payload")
        return

    try:
        plan_id = uuid.UUID(payload.split(":", 1)[1])
    except ValueError:
        await query.answer(ok=False, error_message="Invalid plan")
        return

    from app.models.subscription_plan import SubscriptionPlan

    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None or not plan.is_active:
        await query.answer(ok=False, error_message="Plan no longer available")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message, user: User, lang: str, session: AsyncSession
) -> None:
    payment_info = message.successful_payment
    if payment_info is None:
        return

    payload = payment_info.invoice_payload
    if not payload.startswith("sub:"):
        return

    plan_id = uuid.UUID(payload.split(":", 1)[1])

    payment = Payment(
        user_id=user.id,
        plan_id=plan_id,
        telegram_payment_charge_id=payment_info.telegram_payment_charge_id,
        provider_payment_charge_id=payment_info.provider_payment_charge_id,
        amount_stars=payment_info.total_amount,
        status="completed",
    )
    session.add(payment)

    subscription = await activate_subscription(session, user.id, plan_id, source="payment")
    await session.flush()

    if subscription.is_lifetime:
        await message.answer(t("subscription.activated", lang))
    elif subscription.expires_at:
        date_str = subscription.expires_at.strftime("%d.%m.%Y")
        await message.answer(t("subscription.extended", lang, date=date_str))
    else:
        await message.answer(t("subscription.activated", lang))

    await log_user_action(user.id, "subscription_activated", str(plan_id))
