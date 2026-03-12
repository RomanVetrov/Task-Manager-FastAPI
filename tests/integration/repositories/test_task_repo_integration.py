from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import PriorityEnum, StatusEnum
from app.repositories import task_repo, user_repo
from app.schemas.task import SortOrder, TaskListFilters, TaskSortBy

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_task_repo_crud_cycle(db_session: AsyncSession) -> None:
    """Проверяет полный CRUD-цикл задачи через репозиторий."""
    user = await user_repo.create_user(
        db_session,
        email=f"task-owner-{uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
    )

    created = await task_repo.create_task(
        db_session,
        user,
        title="Repo task",
        description="created by repo test",
    )
    assert created.user_id == user.id

    loaded = await task_repo.get_task_by_id(db_session, created.id)
    assert loaded is not None
    assert loaded.title == "Repo task"

    updated = await task_repo.update_task(
        db_session,
        loaded,
        title="Updated by repo",
        status=StatusEnum.done,
    )
    assert updated.title == "Updated by repo"
    assert updated.status == StatusEnum.done

    deleted_id = await task_repo.delete_task(db_session, updated)
    assert deleted_id == created.id
    assert await task_repo.get_task_by_id(db_session, created.id) is None


@pytest.mark.asyncio
async def test_get_tasks_by_user_filters_foreign_tasks(
    db_session: AsyncSession,
) -> None:
    """Проверяет, что get_tasks_by_user возвращает только задачи указанного пользователя."""
    user_a = await user_repo.create_user(
        db_session,
        email=f"user-a-{uuid4().hex[:8]}@example.com",
        hashed_password="hash-a",
    )
    user_b = await user_repo.create_user(
        db_session,
        email=f"user-b-{uuid4().hex[:8]}@example.com",
        hashed_password="hash-b",
    )
    await task_repo.create_task(db_session, user_a, title="A1")
    await task_repo.create_task(db_session, user_a, title="A2")
    await task_repo.create_task(db_session, user_b, title="B1")

    tasks_a = await task_repo.get_tasks_by_user(db_session, user_a)
    titles = sorted(task.title for task in tasks_a)

    assert titles == ["A1", "A2"]


@pytest.mark.asyncio
async def test_get_tasks_by_user_applies_filters_sorting_and_pagination(
    db_session: AsyncSession,
) -> None:
    """Проверяет фильтрацию, сортировку и пагинацию в get_tasks_by_user."""
    user = await user_repo.create_user(
        db_session,
        email=f"filter-user-{uuid4().hex[:8]}@example.com",
        hashed_password="hash-user",
    )

    await task_repo.create_task(
        db_session,
        user,
        title="Gamma report",
        status=StatusEnum.done,
        priority=PriorityEnum.high,
    )
    await task_repo.create_task(
        db_session,
        user,
        title="Alpha report",
        status=StatusEnum.done,
        priority=PriorityEnum.high,
    )
    await task_repo.create_task(
        db_session,
        user,
        title="Beta draft",
        status=StatusEnum.todo,
        priority=PriorityEnum.low,
    )

    filters = TaskListFilters(
        status=StatusEnum.done,
        priority=PriorityEnum.high,
        q="report",
        sort_by=TaskSortBy.task_title,
        sort_order=SortOrder.asc,
        limit=1,
        offset=1,
    )
    filtered_tasks = await task_repo.get_tasks_by_user(db_session, user, filters)

    assert len(filtered_tasks) == 1
    assert filtered_tasks[0].title == "Gamma report"
