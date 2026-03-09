from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.models.task import Task
from app.schemas.tag import TagCreate, TagUpdate
from app.services import tag as tag_service


@pytest.fixture
def fake_session() -> AsyncSession:
    """Создаёт фейковую AsyncSession для unit-тестов tag_service."""
    return cast(AsyncSession, AsyncMock(spec=AsyncSession))


@pytest.fixture
def existing_tag() -> Tag:
    """Создаёт тестовый объект тега для проверок service-логики."""
    return cast(
        Tag,
        SimpleNamespace(
            id=uuid4(),
            name="backend",
            color="#22AAFF",
            created_at=datetime.now(UTC),
        ),
    )


@pytest.fixture
def existing_task() -> Task:
    """Создаёт тестовый объект задачи для проверок привязки/отвязки тегов."""
    return cast(
        Task,
        SimpleNamespace(
            id=uuid4(),
            title="Task",
            description=None,
            status="todo",
            priority="medium",
            due_date=None,
            user_id=uuid4(),
            created_at=datetime.now(UTC),
        ),
    )


@pytest.mark.asyncio
async def test_create_tag_raises_when_name_already_exists(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что create_tag выбрасывает TagAlreadyExists при конфликте имени."""
    get_tag_by_name = AsyncMock(return_value=existing_tag)
    create_tag = AsyncMock()
    monkeypatch.setattr(
        tag_service.tag_repo, "get_tag_by_name", cast(Any, get_tag_by_name)
    )
    monkeypatch.setattr(tag_service.tag_repo, "create_tag", cast(Any, create_tag))

    with pytest.raises(tag_service.TagAlreadyExists):
        await tag_service.create_tag(
            fake_session,
            payload=TagCreate(name="backend", color="#22AAFF"),
        )

    create_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_tag_delegates_to_repository(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что create_tag делегирует создание в tag_repo при отсутствии конфликта."""
    get_tag_by_name = AsyncMock(return_value=None)
    create_tag = AsyncMock(return_value=existing_tag)
    monkeypatch.setattr(
        tag_service.tag_repo, "get_tag_by_name", cast(Any, get_tag_by_name)
    )
    monkeypatch.setattr(tag_service.tag_repo, "create_tag", cast(Any, create_tag))

    result = await tag_service.create_tag(
        fake_session,
        payload=TagCreate(name="backend", color="#22AAFF"),
    )

    assert result is existing_tag
    create_tag.assert_awaited_once_with(
        fake_session,
        name="backend",
        color="#22AAFF",
    )


@pytest.mark.asyncio
async def test_list_tags_delegates_to_repository(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что list_tags возвращает результат tag_repo.list_tags без изменений."""
    list_tags = AsyncMock(return_value=[existing_tag])
    monkeypatch.setattr(tag_service.tag_repo, "list_tags", cast(Any, list_tags))

    result = await tag_service.list_tags(fake_session)

    assert len(result) == 1
    assert result[0] is existing_tag


@pytest.mark.asyncio
async def test_update_tag_raises_when_new_name_conflicts(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что update_tag выбрасывает TagAlreadyExists при конфликтном rename."""
    get_tag_by_name = AsyncMock(return_value=cast(Tag, SimpleNamespace(id=uuid4())))
    update_tag = AsyncMock()
    monkeypatch.setattr(
        tag_service.tag_repo, "get_tag_by_name", cast(Any, get_tag_by_name)
    )
    monkeypatch.setattr(tag_service.tag_repo, "update_tag", cast(Any, update_tag))

    with pytest.raises(tag_service.TagAlreadyExists):
        await tag_service.update_tag(
            fake_session,
            existing_tag,
            payload=TagUpdate(name="duplicate"),
        )

    update_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tag_skips_conflict_check_for_same_name(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что update_tag не запрашивает конфликт, если имя не меняется."""
    payload = TagUpdate(name=existing_tag.name)
    get_tag_by_name = AsyncMock()
    update_tag = AsyncMock(return_value=existing_tag)
    monkeypatch.setattr(
        tag_service.tag_repo, "get_tag_by_name", cast(Any, get_tag_by_name)
    )
    monkeypatch.setattr(tag_service.tag_repo, "update_tag", cast(Any, update_tag))

    result = await tag_service.update_tag(fake_session, existing_tag, payload)

    assert result is existing_tag
    get_tag_by_name.assert_not_awaited()
    update_tag.assert_awaited_once_with(
        fake_session, existing_tag, name=existing_tag.name
    )


@pytest.mark.asyncio
async def test_delete_tag_returns_repository_id(
    fake_session: AsyncSession,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что delete_tag возвращает id, полученный из репозитория."""
    tag_id = uuid4()
    delete_tag = AsyncMock(return_value=tag_id)
    monkeypatch.setattr(tag_service.tag_repo, "delete_tag", cast(Any, delete_tag))

    result = await tag_service.delete_tag(fake_session, existing_tag)

    assert result == tag_id
    delete_tag.assert_awaited_once_with(fake_session, existing_tag)


@pytest.mark.asyncio
async def test_attach_tag_to_task_delegates_to_repository(
    fake_session: AsyncSession,
    existing_task: Task,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что attach_tag_to_task делегирует вызов в tag_repo."""
    attach_tag_to_task = AsyncMock()
    monkeypatch.setattr(
        tag_service.tag_repo,
        "attach_tag_to_task",
        cast(Any, attach_tag_to_task),
    )

    await tag_service.attach_tag_to_task(fake_session, existing_task, existing_tag)

    attach_tag_to_task.assert_awaited_once_with(
        fake_session, existing_task, existing_tag
    )


@pytest.mark.asyncio
async def test_detach_tag_from_task_delegates_to_repository(
    fake_session: AsyncSession,
    existing_task: Task,
    existing_tag: Tag,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что detach_tag_from_task делегирует вызов в tag_repo."""
    detach_tag_from_task = AsyncMock()
    monkeypatch.setattr(
        tag_service.tag_repo,
        "detach_tag_from_task",
        cast(Any, detach_tag_from_task),
    )

    await tag_service.detach_tag_from_task(fake_session, existing_task, existing_tag)

    detach_tag_from_task.assert_awaited_once_with(
        fake_session, existing_task, existing_tag
    )
