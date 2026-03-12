from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from redis.exceptions import RedisError
from unittest.mock import AsyncMock

from app.cache.tasks_list import (
    delete_cached_tasks_list_for_user,
    build_tasks_list_cache_key,
    get_cached_tasks_list,
    set_cached_tasks_list,
)
from app.models.task import PriorityEnum, StatusEnum
from app.schemas.task import TaskRead


def _make_task_read() -> TaskRead:
    """Создаёт валидный TaskRead для тестов кэш-модуля."""
    return TaskRead(
        id=uuid4(),
        title="Task",
        description="desc",
        status=StatusEnum.todo,
        priority=PriorityEnum.medium,
        due_date=None,
        user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def test_build_tasks_list_cache_key_is_stable_for_filter_order() -> None:
    """Проверяет детерминированность ключа при разном порядке параметров."""
    user_id = uuid4()
    key_a = build_tasks_list_cache_key(
        user_id=user_id,
        filters={"status": "done", "limit": 20, "offset": 0},
    )
    key_b = build_tasks_list_cache_key(
        user_id=user_id,
        filters={"offset": 0, "status": "done", "limit": 20},
    )

    assert key_a == key_b


@pytest.mark.asyncio
async def test_get_cached_tasks_list_returns_none_on_redis_error() -> None:
    """Проверяет отказоустойчивость: ошибка Redis не приводит к исключению."""
    redis = SimpleNamespace(get=AsyncMock(side_effect=RedisError("boom")))

    result = await get_cached_tasks_list(redis, "v1:tasks:list:user:test-key")

    assert result is None


@pytest.mark.asyncio
async def test_set_cached_tasks_list_does_not_raise_on_redis_error() -> None:
    """Проверяет отказоустойчивость при сохранении в Redis."""
    redis = SimpleNamespace(set=AsyncMock(side_effect=RedisError("boom")))

    await set_cached_tasks_list(
        redis,
        "v1:tasks:list:user:test-key",
        [_make_task_read()],
        ttl_seconds=60,
    )


@pytest.mark.asyncio
async def test_get_cached_tasks_list_invalid_payload_triggers_delete() -> None:
    """Проверяет, что битый payload удаляется из кэша."""
    redis = SimpleNamespace(
        get=AsyncMock(return_value="{not-json"),
        delete=AsyncMock(return_value=1),
    )

    result = await get_cached_tasks_list(redis, "v1:tasks:list:user:test-key")

    assert result is None
    redis.delete.assert_awaited_once_with("v1:tasks:list:user:test-key")


@pytest.mark.asyncio
async def test_delete_cached_tasks_list_for_user_deletes_all_user_keys() -> None:
    """Проверяет удаление всех ключей пользователя по префиксу."""
    user_id = uuid4()
    matching_keys = [
        build_tasks_list_cache_key(user_id=user_id, filters={"status": "done"}),
        build_tasks_list_cache_key(user_id=user_id, filters={"priority": "high"}),
    ]

    async def _scan_iter(match: str):
        _ = match
        for key in matching_keys:
            yield key

    redis = SimpleNamespace(
        scan_iter=_scan_iter,
        delete=AsyncMock(return_value=2),
    )

    await delete_cached_tasks_list_for_user(redis, user_id)

    redis.delete.assert_awaited_once_with(*matching_keys)
