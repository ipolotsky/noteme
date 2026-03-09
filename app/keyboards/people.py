from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.loader import t
from app.keyboards.callbacks import MediaPersonCb, MenuCb, PersonCb
from app.keyboards.pagination import pagination_row
from app.models.person import Person

PAGE_SIZE = 10


def people_list_kb(people: list[Person], page: int, total: int, lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for i in range(0, len(people), 2):
        row = [
            InlineKeyboardButton(
                text=f"\U0001f464 {people[i].name}",
                callback_data=PersonCb(action="view", id=str(people[i].id)).pack(),
            )
        ]
        if i + 1 < len(people):
            row.append(
                InlineKeyboardButton(
                    text=f"\U0001f464 {people[i + 1].name}",
                    callback_data=PersonCb(action="view", id=str(people[i + 1].id)).pack(),
                )
            )
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u2795 {t('people.create', lang)}",
                callback_data=PersonCb(action="create").pack(),
            )
        ]
    )

    if total > PAGE_SIZE:
        rows.append(pagination_row("people", page, total, PAGE_SIZE, lang))

    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u25c0 {t('menu.back', lang)}",
                callback_data=MenuCb(action="main").pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def person_view_kb(
    person: Person,
    lang: str,
    events_count: int = 0,
    wishes_count: int = 0,
) -> InlineKeyboardMarkup:
    pid = str(person.id)
    rows: list[list[InlineKeyboardButton]] = []

    browse_row: list[InlineKeyboardButton] = []
    if events_count > 0:
        browse_row.append(
            InlineKeyboardButton(
                text=f"\U0001f4cb {t('people.show_events', lang)} ({events_count})",
                callback_data=PersonCb(action="events", id=pid).pack(),
            )
        )
    if wishes_count > 0:
        browse_row.append(
            InlineKeyboardButton(
                text=f"\U0001f4dd {t('people.show_wishes', lang)} ({wishes_count})",
                callback_data=PersonCb(action="wishes", id=pid).pack(),
            )
        )
    if browse_row:
        rows.append(browse_row)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u270f\ufe0f {t('people.rename', lang)}",
                callback_data=PersonCb(action="rename", id=pid).pack(),
            ),
            InlineKeyboardButton(
                text=f"\U0001f5d1 {t('people.delete', lang)}",
                callback_data=PersonCb(action="delete", id=pid).pack(),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u25c0 {t('menu.back', lang)}",
                callback_data=PersonCb(action="list").pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def person_delete_confirm_kb(person_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("buttons.yes", lang),
                    callback_data=PersonCb(action="confirm_delete", id=person_id).pack(),
                ),
                InlineKeyboardButton(
                    text=t("buttons.no", lang),
                    callback_data=PersonCb(action="view", id=person_id).pack(),
                ),
            ],
        ]
    )


def media_person_select_kb(people: list[Person], lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for i in range(0, len(people), 2):
        row = [
            InlineKeyboardButton(
                text=f"\U0001f464 {people[i].name}",
                callback_data=MediaPersonCb(action="select", id=str(people[i].id)).pack(),
            )
        ]
        if i + 1 < len(people):
            row.append(
                InlineKeyboardButton(
                    text=f"\U0001f464 {people[i + 1].name}",
                    callback_data=MediaPersonCb(action="select", id=str(people[i + 1].id)).pack(),
                )
            )
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u2795 {t('people.create', lang)}",
                callback_data=MediaPersonCb(action="create").pack(),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"\u2716 {t('menu.cancel', lang)}",
                callback_data=MediaPersonCb(action="cancel").pack(),
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
