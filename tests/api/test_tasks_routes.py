from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app import get_or_404
from app.cache import build_tasks_list_cache_key
from app.models.tag import Tag
from app.models.task import PriorityEnum, StatusEnum, Task
from app.models.user import User
from app.routes import tasks as tasks_routes
from app.schemas.task import TaskListFilters, TaskUpdate

pytestmark = pytest.mark.asyncio


def _make_user(*, is_active: bool = True) -> User:
    """Создаёт тестового пользователя."""
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            email="user@example.com",
            hashed_password="hashed",
            is_active=is_active,
            created_at=datetime.now(UTC),
        ),
    )


def _make_task(user: User, **overrides: object) -> Task:
    """Создаёт тестовую задачу с возможностью переопределения полей."""
    data = {
        "id": uuid4(),
        "title": "Task title",
        "description": "Task description",
        "status": StatusEnum.todo,
        "priority": PriorityEnum.medium,
        "due_date": None,
        "user_id": user.id,
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return cast(Task, SimpleNamespace(**data))


def _make_tag(**overrides: object) -> Tag:
    """Создаёт тестовый тег с возможностью переопределения полей."""
    data = {
        "id": uuid4(),
        "name": "backend",
        "color": "#22AAFF",
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return cast(Tag, SimpleNamespace(**data))


def _default_list_filters_payload() -> dict[str, object]:
    """Возвращает дефолтный набор query-параметров для GET /tasks."""
    return TaskListFilters().model_dump(mode="json", exclude_none=True)


async def test_create_task_returns_201(
    client: AsyncClient,
    fake_session: object,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешное создание задачи и корректную передачу аргументов в service."""
    default_key = build_tasks_list_cache_key(
        user_id=current_user.id,
        filters=_default_list_filters_payload(),
    )
    filtered_key = build_tasks_list_cache_key(
        user_id=current_user.id,
        filters={"status": "done", "limit": 20, "offset": 0},
    )
    fake_redis.store[default_key] = "cached-default"
    fake_redis.store[filtered_key] = "cached-filtered"

    created_task = _make_task(current_user, title="New task")
    create_task = AsyncMock(return_value=created_task)
    monkeypatch.setattr(tasks_routes.task_service, "create_task", create_task)

    response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "New task",
            "description": "desc",
            "status": "todo",
            "priority": "medium",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New task"
    create_task.assert_awaited_once()
    create_task_call = create_task.await_args
    assert create_task_call is not None
    assert create_task_call.args[0] is fake_session
    assert create_task_call.args[1] is current_user
    assert default_key not in fake_redis.store
    assert filtered_key not in fake_redis.store


async def test_create_task_returns_400_for_past_due_date(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что создание задачи с дедлайном в прошлом возвращает 400."""
    create_task = AsyncMock(side_effect=tasks_routes.InvalidDueDate)
    monkeypatch.setattr(tasks_routes.task_service, "create_task", create_task)

    response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Task",
            "due_date": (date.today() - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Дедлайн не может быть в прошлом"


async def test_list_tasks_returns_only_current_user_tasks(
    client: AsyncClient,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что список задач возвращается для текущего пользователя."""
    tasks = [
        _make_task(current_user, title="One"),
        _make_task(current_user, title="Two"),
    ]
    get_user_tasks = AsyncMock(return_value=tasks)
    monkeypatch.setattr(tasks_routes.task_service, "get_user_tasks", get_user_tasks)

    response = await client.get("/api/v1/tasks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {item["title"] for item in body} == {"One", "Two"}
    assert len(fake_redis.set_calls) == 1
    assert fake_redis.set_calls[0][0] == build_tasks_list_cache_key(
        user_id=current_user.id,
        filters=_default_list_filters_payload(),
    )


async def test_list_tasks_uses_cache_on_second_call(
    client: AsyncClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что второй GET /tasks берёт данные из Redis, не из service."""
    tasks = [_make_task(current_user, title="Cached title")]
    get_user_tasks = AsyncMock(return_value=tasks)
    monkeypatch.setattr(tasks_routes.task_service, "get_user_tasks", get_user_tasks)

    first_response = await client.get("/api/v1/tasks")
    second_response = await client.get("/api/v1/tasks")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()[0]["title"] == "Cached title"
    assert get_user_tasks.await_count == 1


async def test_list_tasks_reads_preloaded_cache_without_service_call(
    client: AsyncClient,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет попадание в кэш: ручка отдаёт данные из Redis без вызова сервиса."""
    cached_task = _make_task(current_user, title="From cache")
    payload = [
        tasks_routes.TaskRead.model_validate(cached_task).model_dump(mode="json")
    ]
    fake_redis.store[
        build_tasks_list_cache_key(
            user_id=current_user.id,
            filters=_default_list_filters_payload(),
        )
    ] = json.dumps(payload)

    get_user_tasks = AsyncMock()
    monkeypatch.setattr(tasks_routes.task_service, "get_user_tasks", get_user_tasks)

    response = await client.get("/api/v1/tasks")

    assert response.status_code == 200
    assert response.json()[0]["title"] == "From cache"
    get_user_tasks.assert_not_awaited()


async def test_list_tasks_falls_back_to_service_when_redis_is_unavailable(
    client: AsyncClient,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет отказоустойчивость: при падении Redis список читается из сервиса."""
    fake_redis.raise_on_get = True
    tasks = [_make_task(current_user, title="Fallback")]
    get_user_tasks = AsyncMock(return_value=tasks)
    monkeypatch.setattr(tasks_routes.task_service, "get_user_tasks", get_user_tasks)

    response = await client.get("/api/v1/tasks")

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Fallback"
    get_user_tasks.assert_awaited_once()


async def test_list_tasks_passes_filters_to_service(
    client: AsyncClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что query-параметры фильтрации доходят до сервисного слоя."""
    get_user_tasks = AsyncMock(return_value=[_make_task(current_user)])
    monkeypatch.setattr(tasks_routes.task_service, "get_user_tasks", get_user_tasks)

    response = await client.get(
        "/api/v1/tasks",
        params={
            "status": "done",
            "priority": "high",
            "q": "report",
            "sort_by": "title",
            "sort_order": "asc",
            "limit": 7,
            "offset": 3,
        },
    )

    assert response.status_code == 200
    args = get_user_tasks.await_args
    assert args is not None
    filters = args.args[2]
    assert isinstance(filters, TaskListFilters)
    assert filters.status is not None and filters.status.value == "done"
    assert filters.priority is not None and filters.priority.value == "high"
    assert filters.q == "report"
    assert filters.sort_by.value == "title"
    assert filters.sort_order.value == "asc"
    assert filters.limit == 7
    assert filters.offset == 3


async def test_list_tasks_returns_422_for_invalid_due_date_range(
    client: AsyncClient,
) -> None:
    """Проверяет валидацию диапазона дат: due_after > due_before недопустим."""
    response = await client.get(
        "/api/v1/tasks",
        params={
            "due_after": "2026-12-31",
            "due_before": "2026-01-01",
        },
    )

    assert response.status_code == 422


async def test_get_task_returns_200_for_owner(
    client: AsyncClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет доступ владельца к своей задаче по id (200)."""
    task = _make_task(current_user, title="Owned")
    get_task_by_id = AsyncMock(return_value=task)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)

    response = await client.get(f"/api/v1/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Owned"


async def test_get_task_returns_404_when_not_found(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что запрос несуществующей задачи возвращает 404."""
    get_task_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)

    response = await client.get(f"/api/v1/tasks/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Задача не найдена"


async def test_get_task_returns_403_for_foreign_owner(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что чужая задача недоступна и возвращает 403."""
    foreign_user = _make_user()
    foreign_task = _make_task(foreign_user)
    get_task_by_id = AsyncMock(return_value=foreign_task)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)

    response = await client.get(f"/api/v1/tasks/{foreign_task.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Нет доступа"


async def test_update_task_returns_200(
    client: AsyncClient,
    fake_session: object,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешный PATCH задачи и передачу TaskUpdate в service."""
    original = _make_task(current_user, title="Old")
    updated = _make_task(current_user, id=original.id, title="Updated")
    get_task_by_id = AsyncMock(return_value=original)
    update_task = AsyncMock(return_value=updated)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)
    monkeypatch.setattr(tasks_routes.task_service, "update_task", update_task)

    response = await client.patch(
        f"/api/v1/tasks/{original.id}",
        json={"title": "Updated"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    update_task.assert_awaited_once()
    update_task_call = update_task.await_args
    assert update_task_call is not None
    assert update_task_call.args[0] is fake_session
    assert update_task_call.args[1] is original
    assert isinstance(update_task_call.args[2], TaskUpdate)
    assert update_task_call.args[2].title == "Updated"
    assert fake_redis.delete_calls == [
        build_tasks_list_cache_key(user_id=current_user.id)
    ]


async def test_update_task_returns_400_for_past_due_date(
    client: AsyncClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что PATCH с дедлайном в прошлом возвращает 400."""
    task = _make_task(current_user)
    get_task_by_id = AsyncMock(return_value=task)
    update_task = AsyncMock(side_effect=tasks_routes.InvalidDueDate)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)
    monkeypatch.setattr(tasks_routes.task_service, "update_task", update_task)

    response = await client.patch(
        f"/api/v1/tasks/{task.id}",
        json={"due_date": (date.today() - timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Дедлайн не может быть в прошлом"


async def test_delete_task_returns_deleted_id(
    client: AsyncClient,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешное удаление задачи и возврат ее id."""
    task = _make_task(current_user)
    get_task_by_id = AsyncMock(return_value=task)
    delete_task = AsyncMock(return_value=task.id)
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)
    monkeypatch.setattr(tasks_routes.task_service, "delete_task", delete_task)

    response = await client.delete(f"/api/v1/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json() == {"id": str(task.id)}
    assert fake_redis.delete_calls == [
        build_tasks_list_cache_key(user_id=current_user.id)
    ]


async def test_attach_tag_to_task_returns_201(
    client: AsyncClient,
    fake_session: object,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешную привязку тега к задаче (201)."""
    task = _make_task(current_user)
    tag = _make_tag()
    get_task_by_id = AsyncMock(return_value=task)
    get_tag_by_id = AsyncMock(return_value=tag)
    attach_tag = AsyncMock()
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)
    monkeypatch.setattr(tasks_routes.tag_service, "attach_tag_to_task", attach_tag)

    response = await client.post(f"/api/v1/tasks/{task.id}/tags/{tag.id}")

    assert response.status_code == 201
    assert response.json() == {"task_id": str(task.id), "tag_id": str(tag.id)}
    attach_tag.assert_awaited_once_with(fake_session, task, tag)
    assert fake_redis.delete_calls == [
        build_tasks_list_cache_key(user_id=current_user.id)
    ]


async def test_detach_tag_from_task_returns_200(
    client: AsyncClient,
    fake_session: object,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешную отвязку тега от задачи (200)."""
    task = _make_task(current_user)
    tag = _make_tag()
    get_task_by_id = AsyncMock(return_value=task)
    get_tag_by_id = AsyncMock(return_value=tag)
    detach_tag = AsyncMock()
    monkeypatch.setattr(get_or_404.task_repo, "get_task_by_id", get_task_by_id)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)
    monkeypatch.setattr(tasks_routes.tag_service, "detach_tag_from_task", detach_tag)

    response = await client.delete(f"/api/v1/tasks/{task.id}/tags/{tag.id}")

    assert response.status_code == 200
    assert response.json() == {"task_id": str(task.id), "tag_id": str(tag.id)}
    detach_tag.assert_awaited_once_with(fake_session, task, tag)
    assert fake_redis.delete_calls == [
        build_tasks_list_cache_key(user_id=current_user.id)
    ]


async def test_create_task_returns_201_when_cache_invalidation_fails(
    client: AsyncClient,
    fake_redis,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет отказоустойчивость: сбой Redis на delete не ломает создание задачи."""
    fake_redis.raise_on_delete = True
    created_task = _make_task(current_user, title="Task despite redis failure")
    create_task = AsyncMock(return_value=created_task)
    monkeypatch.setattr(tasks_routes.task_service, "create_task", create_task)

    response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Task despite redis failure",
            "status": "todo",
            "priority": "medium",
        },
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Task despite redis failure"
