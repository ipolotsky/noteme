import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.wish import Wish
from app.schemas.wish import WishCreate, WishUpdate
from app.services.person_service import get_or_create_people


class WishLimitError(Exception):
    def __init__(self, max_wishes: int):
        self.max_wishes = max_wishes
        super().__init__(f"Wish limit reached: {max_wishes}")


async def get_wish(
    session: AsyncSession, wish_id: uuid.UUID, user_id: int | None = None
) -> Wish | None:
    stmt = (
        select(Wish)
        .options(selectinload(Wish.people), selectinload(Wish.media_link))
        .where(Wish.id == wish_id)
    )
    if user_id is not None:
        stmt = stmt.where(Wish.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_wishes(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 10
) -> list[Wish]:
    result = await session.execute(
        select(Wish)
        .options(selectinload(Wish.people), selectinload(Wish.media_link))
        .where(Wish.user_id == user_id)
        .order_by(Wish.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def count_user_wishes(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Wish).where(Wish.user_id == user_id)
    )
    return result.scalar_one()


async def create_wish(
    session: AsyncSession, user_id: int, data: WishCreate
) -> Wish:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    count = await count_user_wishes(session, user_id)
    if count >= user.max_wishes:
        raise WishLimitError(user.max_wishes)

    people = []
    if data.person_names:
        people = await get_or_create_people(session, user_id, data.person_names)

    wish = Wish(
        user_id=user_id,
        text=data.text,
        reminder_date=data.reminder_date,
        people=people,
    )
    session.add(wish)
    await session.flush()

    return wish


async def update_wish(
    session: AsyncSession, wish_id: uuid.UUID, data: WishUpdate, user_id: int | None = None
) -> Wish | None:
    wish = await get_wish(session, wish_id, user_id=user_id)
    if wish is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    person_names = update_data.pop("person_names", None)

    for field, value in update_data.items():
        setattr(wish, field, value)

    if person_names is not None:
        people = await get_or_create_people(session, wish.user_id, person_names)
        wish.people = people

    await session.flush()
    return wish


async def delete_wish(
    session: AsyncSession, wish_id: uuid.UUID, user_id: int | None = None
) -> bool:
    wish = await get_wish(session, wish_id, user_id=user_id)
    if wish is None:
        return False
    await session.delete(wish)
    await session.flush()
    return True


async def create_wish_with_media(
    session: AsyncSession,
    user_id: int,
    text: str,
    person_names: list[str],
    chat_id: int,
    message_id: int,
    media_type: str,
) -> Wish:
    from app.models.media_link import MediaLink

    wish = await create_wish(
        session, user_id, WishCreate(text=text, person_names=person_names)
    )

    media_link = MediaLink(
        wish_id=wish.id,
        chat_id=chat_id,
        message_id=message_id,
        media_type=media_type,
    )
    session.add(media_link)
    await session.flush()

    return wish


async def get_wishes_by_person_names(
    session: AsyncSession, user_id: int, person_names: list[str], limit: int = 5
) -> list[Wish]:
    from app.models.person import Person
    from app.models.wish import WishPerson

    result = await session.execute(
        select(Wish)
        .options(selectinload(Wish.media_link))
        .join(WishPerson, Wish.id == WishPerson.wish_id)
        .join(Person, WishPerson.person_id == Person.id)
        .where(
            Wish.user_id == user_id,
            func.lower(Person.name).in_([n.lower() for n in person_names]),
        )
        .distinct()
        .limit(limit)
    )
    return list(result.scalars().all())
