from __future__ import annotations

import asyncio
from logging import getLogger
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import (
    build_tasks_list_cache_key,
    delete_cached_tasks_list_for_user,
    get_cached_tasks_list,
    set_cached_tasks_list,
)
from app.config import settings
from app.database import get_db
from app.get_or_404 import CurrentUser, TagDep, TaskDep
from app.redis import get_redis
from app.schemas.tag import TaskTagLink
from app.services import tag as tag_service
from app.schemas.task import (
    TaskCreate,
    TaskDeleted,
    TaskListFilters,
    TaskRead,
    TaskUpdate,
)
from app.services import task as task_service
from app.services.task import InvalidDueDate

router = APIRouter(prefix="/tasks", tags=["tasks"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
TaskFilters = Annotated[TaskListFilters, Depends()]
logger = getLogger(__name__)
_BACKGROUND_CACHE_INVALIDATION_TASKS: set[asyncio.Task[None]] = set()

_DUE_DATE_ERROR = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Дедлайн не может быть в прошлом",
)


def _track_background_task(task: asyncio.Task[None]) -> None:
    """Сохраняет strong reference на фоновую задачу до её завершения."""
    _BACKGROUND_CACHE_INVALIDATION_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_CACHE_INVALIDATION_TASKS.discard)


def _schedule_invalidate_user_tasks_cache(redis: Redis, user_id: UUID) -> None:
    """Запускает инвалидацию кэша списка задач в фоне (fire-and-forget).
    Исключения в фоновой задаче логируются и не пробрасываются в вызывающий код.
    """

    async def _run() -> None:
        try:
            await delete_cached_tasks_list_for_user(redis, user_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Не удалось инвалидировать кэш задач пользователя",
                extra={"user_id": str(user_id)},
                exc_info=True,
            )

    _track_background_task(asyncio.create_task(_run()))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
)
async def create_task(
    payload: TaskCreate,
    current_user: CurrentUser,
    session: DbSession,
    redis: RedisClient,
) -> TaskRead:
    try:
        task = await task_service.create_task(session, current_user, payload)
    except InvalidDueDate:
        raise _DUE_DATE_ERROR
    _schedule_invalidate_user_tasks_cache(redis, current_user.id)
    return TaskRead.model_validate(task)


@router.get(
    "",
    summary="Список задач текущего пользователя",
)
async def list_tasks(
    current_user: CurrentUser,
    filters: TaskFilters,
    session: DbSession,
    redis: RedisClient,
) -> list[TaskRead]:
    if (
        filters.due_after is not None
        and filters.due_before is not None
        and filters.due_after > filters.due_before
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="due_after не может быть позже due_before",
        )

    cache_key = build_tasks_list_cache_key(
        user_id=current_user.id,
        filters=filters.model_dump(mode="json", exclude_none=True),
    )
    cached_tasks = await get_cached_tasks_list(redis, cache_key)
    if cached_tasks is not None:
        return cached_tasks

    tasks = await task_service.get_user_tasks(session, current_user, filters)
    response = [TaskRead.model_validate(t) for t in tasks]
    await set_cached_tasks_list(
        redis,
        cache_key,
        response,
        ttl_seconds=settings.TASKS_LIST_CACHE_TTL_SECONDS,
    )
    return response


@router.get(
    "/{task_id}",
    summary="Получить задачу по id",
)
async def get_task(task: TaskDep) -> TaskRead:
    return TaskRead.model_validate(task)


@router.patch(
    "/{task_id}",
    summary="Обновить задачу",
)
async def update_task(
    payload: TaskUpdate,
    task: TaskDep,
    session: DbSession,
    redis: RedisClient,
) -> TaskRead:
    try:
        updated = await task_service.update_task(session, task, payload)
    except InvalidDueDate:
        raise _DUE_DATE_ERROR
    _schedule_invalidate_user_tasks_cache(redis, task.user_id)
    return TaskRead.model_validate(updated)


@router.delete(
    "/{task_id}",
    summary="Удалить задачу",
)
async def delete_task(
    task: TaskDep,
    session: DbSession,
    redis: RedisClient,
) -> TaskDeleted:
    task_id = await task_service.delete_task(session, task)
    _schedule_invalidate_user_tasks_cache(redis, task.user_id)
    return TaskDeleted(id=task_id)


@router.post(
    "/{task_id}/tags/{tag_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Привязать тег к задаче",
)
async def attach_tag_to_task(
    task: TaskDep,
    tag: TagDep,
    session: DbSession,
    redis: RedisClient,
) -> TaskTagLink:
    await tag_service.attach_tag_to_task(session, task, tag)
    _schedule_invalidate_user_tasks_cache(redis, task.user_id)
    return TaskTagLink(task_id=task.id, tag_id=tag.id)


@router.delete(
    "/{task_id}/tags/{tag_id}",
    summary="Отвязать тег от задачи",
)
async def detach_tag_from_task(
    task: TaskDep,
    tag: TagDep,
    session: DbSession,
    redis: RedisClient,
) -> TaskTagLink:
    await tag_service.detach_tag_from_task(session, task, tag)
    _schedule_invalidate_user_tasks_cache(redis, task.user_id)
    return TaskTagLink(task_id=task.id, tag_id=tag.id)
