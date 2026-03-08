from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User


async def get_task_by_id(session: AsyncSession, task_id: UUID) -> Task | None:
    """Возвращает задачу по id или None."""
    return await session.get(Task, task_id)


async def get_tasks_by_user(session: AsyncSession, user: User) -> Sequence[Task]:
    """Возвращает все задачи пользователя."""
    result = await session.execute(select(Task).where(Task.user_id == user.id))
    return result.scalars().all()


async def create_task(session: AsyncSession, user: User, **data) -> Task:
    """Создаёт задачу для пользователя."""
    task = Task(**data, user_id=user.id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(session: AsyncSession, task: Task, **data) -> Task:
    """Обновляет переданные поля задачи."""
    for field, value in data.items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task: Task) -> UUID:
    """Удаляет задачу и возвращает её id."""
    task_id = task.id
    await session.delete(task)
    await session.commit()
    return task_id
