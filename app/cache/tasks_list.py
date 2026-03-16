from __future__ import annotations

from collections.abc import Mapping
from logging import getLogger
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.metrics import observe_tasks_cache_hit, observe_tasks_cache_miss
from app.schemas.task import TaskRead

logger = getLogger(__name__)
_CACHE_KEY_VERSION = "v1"
_TASKS_LIST_ADAPTER = TypeAdapter(list[TaskRead])


def build_tasks_list_cache_prefix(*, user_id: UUID) -> str:
    """Формирует базовый префикс ключей кэша списка задач пользователя."""
    return f"{_CACHE_KEY_VERSION}:tasks:list:user:{user_id}"


def build_tasks_list_cache_key(
    *,
    user_id: UUID,
    filters: Mapping[str, object | None] | None = None,
) -> str:
    """Формирует ключ кэша списка задач пользователя.

    Параметр filters заложен заранее, чтобы позже безопасно добавить фильтрацию.
    """
    key = build_tasks_list_cache_prefix(user_id=user_id)
    if not filters:
        return key

    normalized = [
        f"{name}={value}"
        for name, value in sorted(filters.items())
        if value is not None
    ]
    if not normalized:
        return key
    return f"{key}:{'&'.join(normalized)}"


async def get_cached_tasks_list(redis: Redis, cache_key: str) -> list[TaskRead] | None:
    """Читает список задач из Redis.

    Любые ошибки Redis не ломают API, а просто отключают кэш на текущем запросе.
    """
    try:
        raw_payload = await redis.get(cache_key)
    except RedisError:
        observe_tasks_cache_miss()
        logger.warning(
            "Не удалось прочитать кэш списка задач",
            extra={"cache_key": cache_key},
        )
        return None

    if raw_payload is None:
        observe_tasks_cache_miss()
        return None

    try:
        tasks = _TASKS_LIST_ADAPTER.validate_json(raw_payload)
        observe_tasks_cache_hit()
        return tasks
    except ValidationError:
        observe_tasks_cache_miss()
        await delete_cached_tasks_list(redis, cache_key)
        return None


async def set_cached_tasks_list(
    redis: Redis,
    cache_key: str,
    tasks: list[TaskRead],
    *,
    ttl_seconds: int,
) -> None:
    """Сохраняет список задач в Redis."""
    try:
        payload = _TASKS_LIST_ADAPTER.dump_json(tasks).decode("utf-8")
        await redis.set(cache_key, payload, ex=ttl_seconds)
    except RedisError:
        logger.warning(
            "Не удалось записать кэш списка задач",
            extra={"cache_key": cache_key},
        )


async def delete_cached_tasks_list(redis: Redis, cache_key: str) -> None:
    """Удаляет кэш списка задач по ключу."""
    try:
        await redis.delete(cache_key)
    except RedisError:
        logger.warning(
            "Не удалось удалить кэш списка задач",
            extra={"cache_key": cache_key},
        )


async def delete_cached_tasks_list_for_user(redis: Redis, user_id: UUID) -> None:
    """Удаляет все кэш-ключи списка задач для пользователя (включая фильтры)."""
    prefix = build_tasks_list_cache_prefix(user_id=user_id)
    pattern = f"{prefix}*"
    try:
        keys = [key async for key in redis.scan_iter(match=pattern)]
        if keys:
            await redis.delete(*keys)
        else:
            await redis.delete(prefix)
    except RedisError:
        logger.warning(
            "Не удалось удалить кэш списка задач по префиксу",
            extra={"cache_key_pattern": pattern},
        )
