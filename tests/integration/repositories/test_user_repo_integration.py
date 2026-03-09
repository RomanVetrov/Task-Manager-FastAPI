from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_and_get_user_by_email(db_session: AsyncSession) -> None:
    """Проверяет создание пользователя в repo и последующую загрузку по email."""
    email = f"user-{uuid4().hex[:8]}@example.com"
    created = await user_repo.create_user(
        db_session,
        email=email,
        hashed_password="hashed-password",
    )

    loaded = await user_repo.get_user_by_email(db_session, email)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.email == email


@pytest.mark.asyncio
async def test_get_user_by_id_returns_none_for_unknown_id(
    db_session: AsyncSession,
) -> None:
    """Проверяет, что repo возвращает None для несуществующего user_id."""
    loaded = await user_repo.get_user_by_id(db_session, uuid4())

    assert loaded is None


@pytest.mark.asyncio
async def test_create_user_enforces_unique_email(db_session: AsyncSession) -> None:
    """Проверяет уникальность email на уровне БД при повторном create_user."""
    email = f"user-{uuid4().hex[:8]}@example.com"
    await user_repo.create_user(
        db_session,
        email=email,
        hashed_password="hash-1",
    )

    with pytest.raises(IntegrityError):
        await user_repo.create_user(
            db_session,
            email=email,
            hashed_password="hash-2",
        )

    await db_session.rollback()
