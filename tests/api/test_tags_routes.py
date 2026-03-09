from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app import get_or_404
from app.models.tag import Tag
from app.routes import tags as tags_routes

pytestmark = pytest.mark.asyncio


def _make_tag(**overrides: object) -> Tag:
    data = {
        "id": uuid4(),
        "name": "backend",
        "color": "#22AAFF",
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return cast(Tag, SimpleNamespace(**data))


async def test_create_tag_returns_201(
    client: AsyncClient,
    fake_session: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешное создание тега и делегирование в service."""
    created_tag = _make_tag(name="python")
    create_tag = AsyncMock(return_value=created_tag)
    monkeypatch.setattr(tags_routes.tag_service, "create_tag", create_tag)

    response = await client.post(
        "/api/v1/tags",
        json={"name": "python", "color": "#3572A5"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "python"
    create_tag.assert_awaited_once()
    create_tag_call = create_tag.await_args
    assert create_tag_call is not None
    assert create_tag_call.args[0] is fake_session


async def test_create_tag_returns_409_when_name_exists(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что конфликт имени тега возвращает 409."""
    create_tag = AsyncMock(side_effect=tags_routes.TagAlreadyExists)
    monkeypatch.setattr(tags_routes.tag_service, "create_tag", create_tag)

    response = await client.post(
        "/api/v1/tags",
        json={"name": "python", "color": "#3572A5"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Тег с таким именем уже существует"


async def test_list_tags_returns_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешную выдачу списка тегов."""
    tags = [_make_tag(name="one"), _make_tag(name="two")]
    list_tags = AsyncMock(return_value=tags)
    monkeypatch.setattr(tags_routes.tag_service, "list_tags", list_tags)

    response = await client.get("/api/v1/tags")

    assert response.status_code == 200
    assert {tag["name"] for tag in response.json()} == {"one", "two"}


async def test_get_tag_returns_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет получение существующего тега по id."""
    tag = _make_tag(name="python")
    get_tag_by_id = AsyncMock(return_value=tag)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)

    response = await client.get(f"/api/v1/tags/{tag.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "python"


async def test_get_tag_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что несуществующий тег возвращает 404."""
    get_tag_by_id = AsyncMock(return_value=None)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)

    response = await client.get(f"/api/v1/tags/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Тег не найден"


async def test_update_tag_returns_200(
    client: AsyncClient,
    fake_session: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешный PATCH тега и передачу аргументов в service."""
    tag = _make_tag(name="old")
    updated_tag = _make_tag(id=tag.id, name="new")
    get_tag_by_id = AsyncMock(return_value=tag)
    update_tag = AsyncMock(return_value=updated_tag)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)
    monkeypatch.setattr(tags_routes.tag_service, "update_tag", update_tag)

    response = await client.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "new"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "new"
    update_tag.assert_awaited_once()
    update_tag_call = update_tag.await_args
    assert update_tag_call is not None
    assert update_tag_call.args[0] is fake_session
    assert update_tag_call.args[1] is tag


async def test_update_tag_returns_409_when_name_conflicts(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что PATCH тега с конфликтным именем возвращает 409."""
    tag = _make_tag(name="old")
    get_tag_by_id = AsyncMock(return_value=tag)
    update_tag = AsyncMock(side_effect=tags_routes.TagAlreadyExists)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)
    monkeypatch.setattr(tags_routes.tag_service, "update_tag", update_tag)

    response = await client.patch(
        f"/api/v1/tags/{tag.id}",
        json={"name": "already-exists"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Тег с таким именем уже существует"


async def test_delete_tag_returns_deleted_id(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет успешное удаление тега и возврат его id."""
    tag = _make_tag()
    get_tag_by_id = AsyncMock(return_value=tag)
    delete_tag = AsyncMock(return_value=tag.id)
    monkeypatch.setattr(get_or_404.tag_repo, "get_tag_by_id", get_tag_by_id)
    monkeypatch.setattr(tags_routes.tag_service, "delete_tag", delete_tag)

    response = await client.delete(f"/api/v1/tags/{tag.id}")

    assert response.status_code == 200
    assert response.json() == {"id": str(tag.id)}
