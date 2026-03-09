from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security import dependences as auth_dep
from app.security.jwt import TokenData, TokenInvalid


@pytest.fixture
def fake_session() -> AsyncSession:
    """Создаёт фейковую AsyncSession для unit-тестов зависимости авторизации."""
    return cast(AsyncSession, AsyncMock(spec=AsyncSession))


def _make_user(*, is_active: bool = True) -> User:
    """Создаёт лёгкий объект пользователя для тестирования веток get_current_user."""
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            email="user@example.com",
            hashed_password="hashed",
            is_active=is_active,
            created_at=datetime.now(UTC),
        ),
    )


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешный путь: валидный токен и активный пользователь возвращаются как результат."""
    user = _make_user(is_active=True)
    decode_access_token = Mock(
        return_value=TokenData(sub=str(user.id), payload={"type": "access"})
    )
    get_user_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_dep, "decode_access_token", cast(Any, decode_access_token))
    monkeypatch.setattr(auth_dep, "get_user_by_id", cast(Any, get_user_by_id))

    result = await auth_dep.get_current_user(token="access-token", session=fake_session)

    assert result is user
    get_user_by_id.assert_awaited_once_with(fake_session, user.id)


@pytest.mark.asyncio
async def test_get_current_user_raises_401_for_invalid_token(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что невалидный токен приводит к 401 и заголовку WWW-Authenticate."""
    decode_access_token = Mock(side_effect=TokenInvalid("bad token"))
    monkeypatch.setattr(auth_dep, "decode_access_token", cast(Any, decode_access_token))

    with pytest.raises(HTTPException) as exc:
        await auth_dep.get_current_user(token="broken-token", session=fake_session)

    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_get_current_user_raises_401_for_invalid_subject(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет ветку с некорректным sub в токене: должен возвращаться 401."""
    decode_access_token = Mock(
        return_value=TokenData(sub="not-a-uuid", payload={"type": "access"})
    )
    monkeypatch.setattr(auth_dep, "decode_access_token", cast(Any, decode_access_token))

    with pytest.raises(HTTPException) as exc:
        await auth_dep.get_current_user(token="access-token", session=fake_session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Некорректный идентификатор в токене"


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_user_not_found(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что при отсутствии пользователя в БД зависимость возвращает 401."""
    user_id = uuid4()
    decode_access_token = Mock(
        return_value=TokenData(sub=str(user_id), payload={"type": "access"})
    )
    get_user_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_dep, "decode_access_token", cast(Any, decode_access_token))
    monkeypatch.setattr(auth_dep, "get_user_by_id", cast(Any, get_user_by_id))

    with pytest.raises(HTTPException) as exc:
        await auth_dep.get_current_user(token="access-token", session=fake_session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Сессия недействительна (пользователь не найден)"


@pytest.mark.asyncio
async def test_get_current_user_raises_403_for_inactive_user(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что неактивный пользователь получает 403 в зависимости get_current_user."""
    user = _make_user(is_active=False)
    decode_access_token = Mock(
        return_value=TokenData(sub=str(user.id), payload={"type": "access"})
    )
    get_user_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_dep, "decode_access_token", cast(Any, decode_access_token))
    monkeypatch.setattr(auth_dep, "get_user_by_id", cast(Any, get_user_by_id))

    with pytest.raises(HTTPException) as exc:
        await auth_dep.get_current_user(token="access-token", session=fake_session)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Аккаунт заблокирован. Обратитесь в поддержку."
