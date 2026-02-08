"""Note service — CRUD with tags, media, and limit checking."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate
from app.services.tag_service import get_or_create_tags


class NoteLimitError(Exception):
    def __init__(self, max_notes: int):
        self.max_notes = max_notes
        super().__init__(f"Note limit reached: {max_notes}")


async def get_note(
    session: AsyncSession, note_id: uuid.UUID, user_id: int | None = None
) -> Note | None:
    stmt = (
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.media_link))
        .where(Note.id == note_id)
    )
    if user_id is not None:
        stmt = stmt.where(Note.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_notes(
    session: AsyncSession, user_id: int, offset: int = 0, limit: int = 10
) -> list[Note]:
    result = await session.execute(
        select(Note)
        .options(selectinload(Note.tags), selectinload(Note.media_link))
        .where(Note.user_id == user_id)
        .order_by(Note.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().unique().all())


async def count_user_notes(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Note).where(Note.user_id == user_id)
    )
    return result.scalar_one()


async def create_note(
    session: AsyncSession, user_id: int, data: NoteCreate
) -> Note:
    # Check limit
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    count = await count_user_notes(session, user_id)
    if count >= user.max_notes:
        raise NoteLimitError(user.max_notes)

    # Resolve tags first (before creating note to avoid lazy-load issues)
    tags = []
    if data.tag_names:
        tags = await get_or_create_tags(session, user_id, data.tag_names)

    note = Note(
        user_id=user_id,
        text=data.text,
        reminder_date=data.reminder_date,
        tags=tags,
    )
    session.add(note)
    await session.flush()

    return note


async def update_note(
    session: AsyncSession, note_id: uuid.UUID, data: NoteUpdate, user_id: int | None = None
) -> Note | None:
    note = await get_note(session, note_id, user_id=user_id)
    if note is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    tag_names = update_data.pop("tag_names", None)

    for field, value in update_data.items():
        setattr(note, field, value)

    if tag_names is not None:
        tags = await get_or_create_tags(session, note.user_id, tag_names)
        note.tags = tags

    await session.flush()
    return note


async def delete_note(
    session: AsyncSession, note_id: uuid.UUID, user_id: int | None = None
) -> bool:
    note = await get_note(session, note_id, user_id=user_id)
    if note is None:
        return False
    await session.delete(note)
    await session.flush()
    return True


async def get_notes_by_tag_names(
    session: AsyncSession, user_id: int, tag_names: list[str], limit: int = 5
) -> list[Note]:
    """Find notes matching any of the given tag names (for feed related notes)."""
    from app.models.note import NoteTag
    from app.models.tag import Tag

    result = await session.execute(
        select(Note)
        .join(NoteTag, Note.id == NoteTag.note_id)
        .join(Tag, NoteTag.tag_id == Tag.id)
        .where(
            Note.user_id == user_id,
            func.lower(Tag.name).in_([n.lower() for n in tag_names]),
        )
        .distinct()
        .limit(limit)
    )
    return list(result.scalars().all())
