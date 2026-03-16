"""API-тесты для dashboard endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.routes import dashboard as dashboard_routes

pytestmark = pytest.mark.asyncio


async def test_dashboard_200_returns_tasks_tags_and_counts(
    client: AsyncClient,
    current_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /dashboard возвращает 200 и тело с tasks, tags, counts_by_status."""
    from app.services import tag as tag_service
    from app.services import task as task_service

    from tests.api.test_tasks_routes import _make_task, _make_tag

    task = _make_task(current_user, title="Dashboard task")
    tag = _make_tag(name="dashboard-tag")
    monkeypatch.setattr(
        task_service,
        "get_user_tasks",
        AsyncMock(return_value=[task]),
    )
    monkeypatch.setattr(
        tag_service,
        "list_tags",
        AsyncMock(return_value=[tag]),
    )
    monkeypatch.setattr(
        dashboard_routes.task_repo,
        "get_task_counts_by_status",
        AsyncMock(return_value={"todo": 1, "in_progress": 0, "done": 0}),
    )

    response = await client.get("/api/v1/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert "tasks" in body
    assert "tags" in body
    assert "counts_by_status" in body
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["title"] == "Dashboard task"
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "dashboard-tag"
    assert body["counts_by_status"] == {"todo": 1, "in_progress": 0, "done": 0}
