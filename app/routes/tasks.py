from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_or_404 import CurrentUser, TagDep, TaskDep
from app.schemas.tag import TaskTagLink
from app.services import tag as tag_service
from app.schemas.task import TaskCreate, TaskDeleted, TaskRead, TaskUpdate
from app.services import task as task_service
from app.services.task import InvalidDueDate

router = APIRouter(prefix="/tasks", tags=["tasks"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

_DUE_DATE_ERROR = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Дедлайн не может быть в прошлом",
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
)
async def create_task(
    payload: TaskCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskRead:
    try:
        task = await task_service.create_task(session, current_user, payload)
    except InvalidDueDate:
        raise _DUE_DATE_ERROR
    return TaskRead.model_validate(task)


@router.get(
    "",
    summary="Список задач текущего пользователя",
)
async def list_tasks(
    current_user: CurrentUser,
    session: DbSession,
) -> list[TaskRead]:
    tasks = await task_service.get_user_tasks(session, current_user)
    return [TaskRead.model_validate(t) for t in tasks]


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
) -> TaskRead:
    try:
        updated = await task_service.update_task(session, task, payload)
    except InvalidDueDate:
        raise _DUE_DATE_ERROR
    return TaskRead.model_validate(updated)


@router.delete(
    "/{task_id}",
    summary="Удалить задачу",
)
async def delete_task(
    task: TaskDep,
    session: DbSession,
) -> TaskDeleted:
    task_id = await task_service.delete_task(session, task)
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
) -> TaskTagLink:
    await tag_service.attach_tag_to_task(session, task, tag)
    return TaskTagLink(task_id=task.id, tag_id=tag.id)


@router.delete(
    "/{task_id}/tags/{tag_id}",
    summary="Отвязать тег от задачи",
)
async def detach_tag_from_task(
    task: TaskDep,
    tag: TagDep,
    session: DbSession,
) -> TaskTagLink:
    await tag_service.detach_tag_from_task(session, task, tag)
    return TaskTagLink(task_id=task.id, tag_id=tag.id)
