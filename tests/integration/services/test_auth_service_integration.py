from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repo
from app.services import auth as auth_service

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_register_user_persists_hashed_password(
    db_session: AsyncSession,
) -> None:
    """Проверяет, что регистрация сохраняет пользователя и хэширует пароль Argon2."""
    user = await auth_service.register_user(
        db_session,
        email="integration-user@example.com",
        password="StrongPass123!",
    )

    assert user.id is not None
    assert user.email == "integration-user@example.com"
    assert user.hashed_password != "StrongPass123!"
    assert user.hashed_password.startswith("$argon2")


@pytest.mark.asyncio
async def test_authenticate_active_user_success(
    db_session: AsyncSession,
) -> None:
    """Проверяет успешную аутентификацию активного пользователя в реальной БД."""
    await auth_service.register_user(
        db_session,
        email="active@example.com",
        password="StrongPass123!",
    )

    authenticated = await auth_service.authenticate_active_user(
        db_session,
        email="active@example.com",
        password="StrongPass123!",
    )

    assert authenticated is not None
    assert authenticated.email == "active@example.com"


@pytest.mark.asyncio
async def test_authenticate_active_user_returns_none_for_wrong_password(
    db_session: AsyncSession,
) -> None:
    """Проверяет, что неверный пароль возвращает None на authenticate_active_user."""
    await auth_service.register_user(
        db_session,
        email="wrong-pass@example.com",
        password="StrongPass123!",
    )

    authenticated = await auth_service.authenticate_active_user(
        db_session,
        email="wrong-pass@example.com",
        password="WrongPass123!",
    )

    assert authenticated is None


@pytest.mark.asyncio
async def test_authenticate_active_user_raises_for_inactive(
    db_session: AsyncSession,
) -> None:
    """Проверяет, что неактивный пользователь вызывает UserInactive."""
    user = await auth_service.register_user(
        db_session,
        email="inactive@example.com",
        password="StrongPass123!",
    )
    user.is_active = False
    await db_session.commit()

    with pytest.raises(auth_service.UserInactive):
        await auth_service.authenticate_active_user(
            db_session,
            email="inactive@example.com",
            password="StrongPass123!",
        )


@pytest.mark.asyncio
async def test_register_user_raises_on_duplicate_email(
    db_session: AsyncSession,
) -> None:
    """Проверяет уникальность email при повторной регистрации."""
    await auth_service.register_user(
        db_session,
        email="dup@example.com",
        password="StrongPass123!",
    )

    with pytest.raises(auth_service.UserAlreadyExists):
        await auth_service.register_user(
            db_session,
            email="dup@example.com",
            password="AnotherPass123!",
        )

    loaded = await user_repo.get_user_by_email(db_session, "dup@example.com")
    assert loaded is not None
