from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.routes import auth as auth_routes
from tests.api.conftest import FakeRedis

pytestmark = pytest.mark.asyncio


def _make_user(email: str, *, is_active: bool = True) -> User:
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            email=email,
            hashed_password="hashed-password",
            is_active=is_active,
            created_at=datetime.now(UTC),
        ),
    )


async def test_register_returns_201_and_user_payload(
    client: AsyncClient,
    fake_session: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешную регистрацию: код 201 и корректный payload пользователя."""
    new_user = _make_user("new@example.com")
    register_user = AsyncMock(return_value=new_user)
    monkeypatch.setattr(auth_routes, "register_user", register_user)

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "strong-pass-123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["is_active"] is True
    register_user.assert_awaited_once_with(
        fake_session,
        "new@example.com",
        "strong-pass-123",
    )


async def test_register_returns_409_when_email_already_exists(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что при конфликте email роут регистрации возвращает 409."""
    register_user = AsyncMock(side_effect=auth_routes.UserAlreadyExists)
    monkeypatch.setattr(auth_routes, "register_user", register_user)

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "existing@example.com", "password": "strong-pass-123"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Пользователь с таким Email уже зарегистрирован"


async def test_login_returns_200_and_token_pair(
    client: AsyncClient,
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешный логин: выдачу пары токенов и запись refresh в Redis."""
    user = _make_user("user@example.com")
    authenticate_active_user = AsyncMock(return_value=user)
    monkeypatch.setattr(
        auth_routes,
        "authenticate_active_user",
        authenticate_active_user,
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert len(fake_redis.set_calls) == 1
    assert fake_redis.set_calls[0][0].startswith(f"rt:{user.id}:")


async def test_login_returns_401_when_credentials_invalid(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что неверные credentials на логине дают 401 и WWW-Authenticate."""
    authenticate_active_user = AsyncMock(return_value=None)
    monkeypatch.setattr(
        auth_routes,
        "authenticate_active_user",
        authenticate_active_user,
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"
    assert response.headers.get("www-authenticate") == "bearer"


async def test_login_returns_403_when_user_inactive(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что заблокированный пользователь получает 403 на логине."""
    authenticate_active_user = AsyncMock(side_effect=auth_routes.UserInactive)
    monkeypatch.setattr(
        auth_routes,
        "authenticate_active_user",
        authenticate_active_user,
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "inactive@example.com", "password": "password-123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Аккаунт заблокирован"


async def test_refresh_returns_401_when_refresh_token_invalid(
    client: AsyncClient,
) -> None:
    """Проверяет, что невалидный refresh-токен отклоняется с 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-jwt"},
    )

    assert response.status_code == 401
    assert "Недействительный" in response.json()["detail"]


async def test_refresh_returns_401_when_subject_is_not_uuid(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что refresh отклоняется с 401 при невалидном user_id в sub."""
    token_data = SimpleNamespace(sub="not-a-uuid", payload={"jti": "jti-1"})
    decode_refresh_token = Mock(return_value=token_data)
    monkeypatch.setattr(auth_routes, "decode_refresh_token", decode_refresh_token)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "any-token"},
    )

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Некорректный идентификатор пользователя в refresh токене"
    )


async def test_refresh_returns_401_when_token_revoked_or_reused(
    client: AsyncClient,
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что отозванный/повторно использованный refresh-токен возвращает 401."""
    user_id = uuid4()
    fake_redis.forced_delete_result = 0
    parse_refresh = Mock(return_value=(user_id, "jti-1"))
    require_active = AsyncMock()
    monkeypatch.setattr(auth_routes, "_parse_refresh_token_or_401", parse_refresh)
    monkeypatch.setattr(auth_routes, "require_active_refresh_user", require_active)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "any-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh токен отозван или уже использован"


async def test_refresh_returns_200_and_rotates_tokens(
    client: AsyncClient,
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет ротацию токенов: старый refresh инвалидируется, новая пара выдается."""
    user = _make_user("user@example.com")
    authenticate_active_user = AsyncMock(return_value=user)
    require_active = AsyncMock()
    monkeypatch.setattr(
        auth_routes,
        "authenticate_active_user",
        authenticate_active_user,
    )
    monkeypatch.setattr(auth_routes, "require_active_refresh_user", require_active)

    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password-123"},
    )
    old_refresh = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["refresh_token"] != old_refresh
    assert len(fake_redis.delete_calls) >= 1
    assert len(fake_redis.set_calls) == 2


async def test_logout_returns_204(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что logout по валидному refresh завершает с 204."""
    user = _make_user("user@example.com")
    authenticate_active_user = AsyncMock(return_value=user)
    require_active = AsyncMock()
    monkeypatch.setattr(
        auth_routes,
        "authenticate_active_user",
        authenticate_active_user,
    )
    monkeypatch.setattr(auth_routes, "require_active_refresh_user", require_active)

    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password-123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 204


async def test_me_returns_current_user_payload(client: AsyncClient) -> None:
    """Проверяет, что /me возвращает данные текущего аутентифицированного пользователя."""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "current@example.com"
    assert body["is_active"] is True
