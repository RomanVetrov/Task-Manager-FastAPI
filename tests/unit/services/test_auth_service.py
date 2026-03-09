from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services import auth as auth_service


@pytest.fixture
def fake_session() -> object:
    return object()


@pytest.fixture
def active_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed-password",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_register_user_raises_when_email_already_exists(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: object,
    active_user: SimpleNamespace,
) -> None:
    get_user_by_email = AsyncMock(return_value=active_user)
    create_user = AsyncMock()

    monkeypatch.setattr(auth_service.user_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth_service.user_repo, "create_user", create_user)

    with pytest.raises(auth_service.UserAlreadyExists):
        await auth_service.register_user(fake_session, "user@example.com", "password")

    create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_user_hashes_password_and_creates_user(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: object,
    active_user: SimpleNamespace,
) -> None:
    get_user_by_email = AsyncMock(return_value=None)
    hash_password = AsyncMock(return_value="hashed-by-test")
    create_user = AsyncMock(return_value=active_user)

    monkeypatch.setattr(auth_service.user_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth_service, "hash_password", hash_password)
    monkeypatch.setattr(auth_service.user_repo, "create_user", create_user)

    created = await auth_service.register_user(
        fake_session,
        "user@example.com",
        "password",
    )

    assert created is active_user
    hash_password.assert_awaited_once_with(password="password")
    create_user.assert_awaited_once_with(
        fake_session,
        email="user@example.com",
        hashed_password="hashed-by-test",
    )


@pytest.mark.asyncio
async def test_authenticate_user_uses_dummy_hash_when_user_not_found(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: object,
) -> None:
    get_user_by_email = AsyncMock(return_value=None)
    get_dummy_hash = Mock(return_value="dummy-hash")
    verify_password = AsyncMock(return_value=False)

    monkeypatch.setattr(auth_service.user_repo, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth_service, "get_dummy_hash", get_dummy_hash)
    monkeypatch.setattr(auth_service, "verify_password", verify_password)

    authenticated = await auth_service.authenticate_user(
        fake_session,
        "missing@example.com",
        "password",
    )

    assert authenticated is None
    verify_password.assert_awaited_once_with(
        password="password",
        hashed_password="dummy-hash",
    )


@pytest.mark.asyncio
async def test_authenticate_active_user_raises_for_inactive_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inactive_user = SimpleNamespace(is_active=False)
    authenticate_user = AsyncMock(return_value=inactive_user)

    monkeypatch.setattr(auth_service, "authenticate_user", authenticate_user)

    with pytest.raises(auth_service.UserInactive):
        await auth_service.authenticate_active_user(
            object(),
            "user@example.com",
            "password",
        )


@pytest.mark.asyncio
async def test_validate_refresh_subject_raises_when_user_not_found(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: object,
) -> None:
    get_user_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_service.user_repo, "get_user_by_id", get_user_by_id)

    with pytest.raises(auth_service.UserNotFound):
        await auth_service.validate_refresh_subject(fake_session, uuid4())


@pytest.mark.asyncio
async def test_validate_refresh_subject_raises_when_user_inactive(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: object,
) -> None:
    inactive_user = SimpleNamespace(is_active=False)
    get_user_by_id = AsyncMock(return_value=inactive_user)
    monkeypatch.setattr(auth_service.user_repo, "get_user_by_id", get_user_by_id)

    with pytest.raises(auth_service.UserInactive):
        await auth_service.validate_refresh_subject(fake_session, uuid4())
