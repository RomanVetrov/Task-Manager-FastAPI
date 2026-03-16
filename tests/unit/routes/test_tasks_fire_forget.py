"""Тесты fire-and-forget инвалидации кэша и обработки исключений в фоновой задаче."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.routes.tasks import _schedule_invalidate_user_tasks_cache

pytestmark = pytest.mark.asyncio


async def test_schedule_invalidate_runs_in_background_and_does_not_propagate_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Исключение в фоновой задаче инвалидации логируется и не пробрасывается в вызывающий код."""
    redis = AsyncMock()
    user_id = uuid4()
    with patch(
        "app.routes.tasks.delete_cached_tasks_list_for_user",
        new_callable=AsyncMock,
        side_effect=Exception("Redis unavailable"),
    ):
        _schedule_invalidate_user_tasks_cache(redis, user_id)
        await asyncio.sleep(0.05)

    assert "Не удалось инвалидировать кэш задач пользователя" in caplog.text
