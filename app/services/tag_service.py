"""Tag service — CRUD, deduplication, case-insensitive matching."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag


class TagLimitError(Exception):
    def __init__(self, max_tags: int):
        self.max_tags = max_tags
        super().__init__(f"Tag limit reached: {max_tags}")


async def get_tag(
    session: AsyncSession, tag_id: uuid.UUID, user_id: int | None = None
) -> Tag | None:
    stmt = select(Tag).where(Tag.id == tag_id)
    if user_id is not None:
        stmt = stmt.where(Tag.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_tag_by_name(session: AsyncSession, user_id: int, name: str) -> Tag | None:
    """Case-insensitive tag lookup."""
    result = await session.execute(
        select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.strip().lower(),
        )
    )
    return result.scalar_one_or_none()


async def get_user_tags(session: AsyncSession, user_id: int) -> list[Tag]:
    result = await session.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    )
    return list(result.scalars().all())


async def create_tag(session: AsyncSession, user_id: int, name: str) -> Tag:
    """Create tag or return existing one (case-insensitive dedup)."""
    name = name.strip()
    existing = await get_tag_by_name(session, user_id, name)
    if existing is not None:
        return existing

    tag = Tag(user_id=user_id, name=name)
    session.add(tag)
    await session.flush()
    return tag


async def get_or_create_tags(
    session: AsyncSession, user_id: int, names: list[str]
) -> list[Tag]:
    """Get or create multiple tags by name (deduplicates input)."""
    seen: set[str] = set()
    tags = []
    for name in names:
        name = name.strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        tag = await create_tag(session, user_id, name)
        tags.append(tag)
    return tags


async def rename_tag(
    session: AsyncSession, tag_id: uuid.UUID, new_name: str, user_id: int | None = None
) -> Tag | None:
    tag = await get_tag(session, tag_id, user_id=user_id)
    if tag is None:
        return None

    # Check if new name already exists for this user
    existing = await get_tag_by_name(session, tag.user_id, new_name)
    if existing is not None and existing.id != tag_id:
        return None  # Conflict

    tag.name = new_name.strip()
    await session.flush()
    return tag


async def delete_tag(
    session: AsyncSession, tag_id: uuid.UUID, user_id: int | None = None
) -> bool:
    tag = await get_tag(session, tag_id, user_id=user_id)
    if tag is None:
        return False
    await session.delete(tag)
    await session.flush()
    return True
