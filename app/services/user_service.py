"""User service — create, update, get users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, data: UserCreate) -> tuple[User, bool]:
    """Get existing user or create new one. Returns (user, created)."""
    user = await get_user(session, data.id)
    if user is not None:
        # Update username/first_name if changed
        changed = False
        if data.username and user.username != data.username:
            user.username = data.username
            changed = True
        if data.first_name and user.first_name != data.first_name:
            user.first_name = data.first_name
            changed = True
        if changed:
            await session.flush()
        return user, False

    user = User(
        id=data.id,
        username=data.username,
        first_name=data.first_name,
        language=data.language,
        max_events=settings.default_max_events,
        max_notes=settings.default_max_notes,
        max_tags_per_entity=settings.default_max_tags_per_entity,
    )
    session.add(user)
    await session.flush()
    return user, True


async def update_user(session: AsyncSession, user_id: int, data: UserUpdate) -> User | None:
    user = await get_user(session, user_id)
    if user is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await session.flush()
    return user
