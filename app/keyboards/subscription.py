from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import SubscribeCb
from app.models.subscription_plan import SubscriptionPlan


def subscription_plans_kb(
    plans: list[SubscriptionPlan], lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        name = plan.name_ru if lang == "ru" else plan.name_en
        price = t("subscription.price_label", lang, stars=str(plan.price_stars))
        label = f"{name} - {price}"
        if plan.discount_percent:
            label += f" {t('subscription.discount_label', lang, percent=str(plan.discount_percent))}"
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=SubscribeCb(action="buy", id=str(plan.id)).pack(),
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=t("subscription.invite_friend", lang),
            callback_data=SubscribeCb(action="referral").pack(),
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def upgrade_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=t("subscription.upgrade_button", lang),
            callback_data=SubscribeCb(action="plans").pack(),
        )],
    ])
