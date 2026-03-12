from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User
from app.schemas.task import SortOrder, TaskListFilters, TaskSortBy


async def get_task_by_id(session: AsyncSession, task_id: UUID) -> Task | None:
    """Возвращает задачу по id или None."""
    return await session.get(Task, task_id)


def _apply_ordering(stmt, filters: TaskListFilters):
    """Добавляет сортировку к запросу списка задач по параметрам фильтра."""
    sort_columns = {
        TaskSortBy.created_at: Task.created_at,
        TaskSortBy.due_date: Task.due_date,
        TaskSortBy.task_title: Task.title,
    }
    sort_column = sort_columns[filters.sort_by]
    order_expression = (
        asc(sort_column) if filters.sort_order == SortOrder.asc else desc(sort_column)
    )
    return stmt.order_by(order_expression)


async def get_tasks_by_user(
    session: AsyncSession,
    user: User,
    filters: TaskListFilters | None = None,
) -> Sequence[Task]:
    """Возвращает список задач пользователя с фильтрами, сортировкой и пагинацией."""
    effective_filters = filters or TaskListFilters()

    stmt = select(Task).where(Task.user_id == user.id)

    if effective_filters.status is not None:
        stmt = stmt.where(Task.status == effective_filters.status)
    if effective_filters.priority is not None:
        stmt = stmt.where(Task.priority == effective_filters.priority)
    if effective_filters.due_after is not None:
        stmt = stmt.where(Task.due_date >= effective_filters.due_after)
    if effective_filters.due_before is not None:
        stmt = stmt.where(Task.due_date <= effective_filters.due_before)

    if effective_filters.q is not None:
        query = effective_filters.q.strip()
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Task.title.ilike(pattern),
                    Task.description.ilike(pattern),
                )
            )

    stmt = _apply_ordering(stmt, effective_filters)
    stmt = stmt.limit(effective_filters.limit).offset(effective_filters.offset)

    result = await session.execute(stmt)
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
