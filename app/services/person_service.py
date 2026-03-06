import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person


class PersonLimitError(Exception):
    def __init__(self, max_people: int):
        self.max_people = max_people
        super().__init__(f"Person limit reached: {max_people}")


async def get_person(
    session: AsyncSession, person_id: uuid.UUID, user_id: int | None = None
) -> Person | None:
    stmt = select(Person).where(Person.id == person_id)
    if user_id is not None:
        stmt = stmt.where(Person.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_person_by_name(session: AsyncSession, user_id: int, name: str) -> Person | None:
    result = await session.execute(
        select(Person).where(
            Person.user_id == user_id,
            func.lower(Person.name) == name.strip().lower(),
        )
    )
    return result.scalar_one_or_none()


async def get_user_people(session: AsyncSession, user_id: int) -> list[Person]:
    result = await session.execute(
        select(Person).where(Person.user_id == user_id).order_by(Person.name)
    )
    return list(result.scalars().all())


async def create_person(session: AsyncSession, user_id: int, name: str) -> Person:
    name = name.strip()
    existing = await get_person_by_name(session, user_id, name)
    if existing is not None:
        return existing

    person = Person(user_id=user_id, name=name)
    session.add(person)
    await session.flush()
    return person


async def get_or_create_people(
    session: AsyncSession, user_id: int, names: list[str]
) -> list[Person]:
    seen: set[str] = set()
    people = []
    for name in names:
        name = name.strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        person = await create_person(session, user_id, name)
        people.append(person)
    return people


async def rename_person(
    session: AsyncSession, person_id: uuid.UUID, new_name: str, user_id: int | None = None
) -> Person | None:
    person = await get_person(session, person_id, user_id=user_id)
    if person is None:
        return None

    existing = await get_person_by_name(session, person.user_id, new_name)
    if existing is not None and existing.id != person_id:
        return None

    person.name = new_name.strip()
    await session.flush()
    return person


async def delete_person(
    session: AsyncSession, person_id: uuid.UUID, user_id: int | None = None
) -> bool:
    person = await get_person(session, person_id, user_id=user_id)
    if person is None:
        return False
    await session.delete(person)
    await session.flush()
    return True
