from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import PriorityEnum, StatusEnum, Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListFilters, TaskUpdate
from app.services import task as task_service


@pytest.fixture
def fake_session() -> AsyncSession:
    return cast(AsyncSession, AsyncMock(spec=AsyncSession))


@pytest.fixture
def active_user() -> User:
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            email="user@example.com",
            hashed_password="hashed-password",
            is_active=True,
        ),
    )


@pytest.fixture
def existing_task(active_user: User) -> Task:
    return cast(
        Task,
        SimpleNamespace(
            id=uuid4(),
            user_id=active_user.id,
            title="Initial title",
            description="Initial description",
            status=StatusEnum.todo,
            priority=PriorityEnum.medium,
            due_date=date.today() + timedelta(days=3),
        ),
    )


@pytest.mark.asyncio
async def test_create_task_calls_repository_with_dumped_payload(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    active_user: User,
    existing_task: Task,
) -> None:
    """Проверяет, что create_task передаёт в репозиторий сериализованный payload."""
    payload = TaskCreate(
        title="New task",
        description="desc",
        status=StatusEnum.in_progress,
        priority=PriorityEnum.high,
        due_date=date.today() + timedelta(days=2),
    )
    create_task = AsyncMock(return_value=existing_task)

    monkeypatch.setattr(task_service.task_repo, "create_task", cast(Any, create_task))

    created = await task_service.create_task(fake_session, active_user, payload)

    assert created is existing_task
    create_task.assert_awaited_once_with(
        fake_session,
        active_user,
        **payload.model_dump(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("days_delta", [-1, -30])
async def test_create_task_raises_for_past_due_date(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    active_user: User,
    days_delta: int,
) -> None:
    """Проверяет, что дедлайн в прошлом отклоняется с InvalidDueDate."""
    payload = TaskCreate(
        title="Task with invalid deadline",
        due_date=date.today() + timedelta(days=days_delta),
    )
    create_task = AsyncMock()
    monkeypatch.setattr(task_service.task_repo, "create_task", cast(Any, create_task))

    with pytest.raises(task_service.InvalidDueDate):
        await task_service.create_task(fake_session, active_user, payload)

    create_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_user_tasks_delegates_to_repository(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    active_user: User,
    existing_task: Task,
) -> None:
    """Проверяет, что get_user_tasks делегирует выборку в репозиторий."""
    tasks = [existing_task]
    get_tasks_by_user = AsyncMock(return_value=tasks)
    monkeypatch.setattr(
        task_service.task_repo,
        "get_tasks_by_user",
        cast(Any, get_tasks_by_user),
    )

    received = await task_service.get_user_tasks(fake_session, active_user)

    assert received == tasks
    get_tasks_by_user.assert_awaited_once()
    call = get_tasks_by_user.await_args
    assert call is not None
    assert call.args[0] is fake_session
    assert call.args[1] is active_user
    assert isinstance(call.args[2], TaskListFilters)
    assert call.args[2] == TaskListFilters()


@pytest.mark.asyncio
async def test_get_user_tasks_passes_custom_filters_to_repository(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    active_user: User,
    existing_task: Task,
) -> None:
    """Проверяет, что кастомные фильтры из service уходят в repository без потерь."""
    tasks = [existing_task]
    filters = TaskListFilters(status=StatusEnum.done, limit=5, offset=10)
    get_tasks_by_user = AsyncMock(return_value=tasks)
    monkeypatch.setattr(
        task_service.task_repo,
        "get_tasks_by_user",
        cast(Any, get_tasks_by_user),
    )

    received = await task_service.get_user_tasks(fake_session, active_user, filters)

    assert received == tasks
    get_tasks_by_user.assert_awaited_once_with(fake_session, active_user, filters)


@pytest.mark.asyncio
async def test_update_task_raises_for_past_due_date(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    existing_task: Task,
) -> None:
    """Проверяет, что update с due_date в прошлом выбрасывает InvalidDueDate."""
    payload = TaskUpdate(due_date=date.today() - timedelta(days=1))
    update_task = AsyncMock()
    monkeypatch.setattr(task_service.task_repo, "update_task", cast(Any, update_task))

    with pytest.raises(task_service.InvalidDueDate):
        await task_service.update_task(fake_session, existing_task, payload)

    update_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_passes_only_explicitly_set_fields(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    existing_task: Task,
) -> None:
    """Проверяет PATCH-поведение: в repo уходят только явно переданные поля."""
    payload = TaskUpdate(title="Renamed")
    update_task = AsyncMock(return_value=existing_task)
    monkeypatch.setattr(task_service.task_repo, "update_task", cast(Any, update_task))

    updated = await task_service.update_task(fake_session, existing_task, payload)

    assert updated is existing_task
    update_task.assert_awaited_once_with(
        fake_session,
        existing_task,
        title="Renamed",
    )


@pytest.mark.asyncio
async def test_update_task_allows_explicit_null_due_date(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    existing_task: Task,
) -> None:
    """Проверяет, что явный due_date=None передаётся в repo как валидное обновление."""
    payload = TaskUpdate(due_date=None)
    update_task = AsyncMock(return_value=existing_task)
    monkeypatch.setattr(task_service.task_repo, "update_task", cast(Any, update_task))

    await task_service.update_task(fake_session, existing_task, payload)

    update_task.assert_awaited_once_with(
        fake_session,
        existing_task,
        due_date=None,
    )


@pytest.mark.asyncio
async def test_delete_task_returns_deleted_id(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: AsyncSession,
    existing_task: Task,
) -> None:
    """Проверяет, что delete_task возвращает id удалённой задачи."""
    task_id = uuid4()
    delete_task = AsyncMock(return_value=task_id)
    monkeypatch.setattr(task_service.task_repo, "delete_task", cast(Any, delete_task))

    deleted_id = await task_service.delete_task(fake_session, existing_task)

    assert deleted_id == task_id
    delete_task.assert_awaited_once_with(fake_session, existing_task)
