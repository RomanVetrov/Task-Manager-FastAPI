from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import refresh_guard
from app.services.auth import UserInactive, UserNotFound


@pytest.fixture
def fake_session() -> AsyncSession:
    """Создаёт фейковую AsyncSession для unit-тестов refresh_guard."""
    return cast(AsyncSession, AsyncMock(spec=AsyncSession))


@pytest.mark.asyncio
async def test_require_active_refresh_user_passes_for_active_user(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешный путь: validate_refresh_subject не выбрасывает исключение."""
    validate_refresh_subject = AsyncMock(return_value=object())
    monkeypatch.setattr(
        refresh_guard,
        "validate_refresh_subject",
        cast(Any, validate_refresh_subject),
    )

    await refresh_guard.require_active_refresh_user(fake_session, uuid4())

    validate_refresh_subject.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_active_refresh_user_maps_not_found_to_401(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что UserNotFound преобразуется в HTTP 401."""
    validate_refresh_subject = AsyncMock(side_effect=UserNotFound)
    monkeypatch.setattr(
        refresh_guard,
        "validate_refresh_subject",
        cast(Any, validate_refresh_subject),
    )

    with pytest.raises(HTTPException) as exc:
        await refresh_guard.require_active_refresh_user(fake_session, uuid4())

    assert exc.value.status_code == 401
    assert exc.value.detail == "Сессия недействительна (пользователь не найден)"


@pytest.mark.asyncio
async def test_require_active_refresh_user_maps_inactive_to_403(
    fake_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что UserInactive преобразуется в HTTP 403."""
    validate_refresh_subject = AsyncMock(side_effect=UserInactive)
    monkeypatch.setattr(
        refresh_guard,
        "validate_refresh_subject",
        cast(Any, validate_refresh_subject),
    )

    with pytest.raises(HTTPException) as exc:
        await refresh_guard.require_active_refresh_user(fake_session, uuid4())

    assert exc.value.status_code == 403
    assert exc.value.detail == "Аккаунт заблокирован"
