from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User
from app.repositories import task_repo
from app.schemas.task import TaskCreate, TaskUpdate


class InvalidDueDate(Exception):
    """Дедлайн задачи не может быть в прошлом."""


async def create_task(session: AsyncSession, user: User, payload: TaskCreate) -> Task:
    """Создаёт задачу. Поднимает InvalidDueDate если дедлайн в прошлом."""
    if payload.due_date and payload.due_date < date.today():
        raise InvalidDueDate
    return await task_repo.create_task(session, user, **payload.model_dump())


async def get_user_tasks(session: AsyncSession, user: User) -> Sequence[Task]:
    """Возвращает все задачи пользователя."""
    return await task_repo.get_tasks_by_user(session, user)


async def update_task(session: AsyncSession, task: Task, payload: TaskUpdate) -> Task:
    """Обновляет задачу. Поднимает InvalidDueDate если дедлайн в прошлом."""
    updates = payload.model_dump(exclude_unset=True)
    due_date = updates.get("due_date")
    if due_date is not None and due_date < date.today():
        raise InvalidDueDate
    return await task_repo.update_task(session, task, **updates)


async def delete_task(session: AsyncSession, task: Task) -> UUID:
    """Удаляет задачу и возвращает её id."""
    return await task_repo.delete_task(session, task)
