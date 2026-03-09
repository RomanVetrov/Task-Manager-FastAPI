from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import task_tags
from app.repositories import tag_repo, task_repo, user_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_tag_repo_create_update_delete_cycle(db_session: AsyncSession) -> None:
    """Проверяет CRUD-цикл тега через репозиторий."""
    tag = await tag_repo.create_tag(
        db_session,
        name=f"tag-{uuid4().hex[:6]}",
        color="#22AAFF",
    )
    assert tag.id is not None

    loaded = await tag_repo.get_tag_by_id(db_session, tag.id)
    assert loaded is not None
    assert loaded.color == "#22AAFF"

    updated = await tag_repo.update_tag(db_session, loaded, name="renamed-tag")
    assert updated.name == "renamed-tag"

    deleted_id = await tag_repo.delete_tag(db_session, updated)
    assert deleted_id == tag.id
    assert await tag_repo.get_tag_by_id(db_session, tag.id) is None


@pytest.mark.asyncio
async def test_list_tags_returns_sorted_by_name(db_session: AsyncSession) -> None:
    """Проверяет сортировку list_tags по имени по возрастанию."""
    await tag_repo.create_tag(db_session, name="zeta", color="#000001")
    await tag_repo.create_tag(db_session, name="alpha", color="#000002")
    await tag_repo.create_tag(db_session, name="beta", color="#000003")

    tags = await tag_repo.list_tags(db_session)
    names = [tag.name for tag in tags]

    assert names == ["alpha", "beta", "zeta"]


@pytest.mark.asyncio
async def test_attach_detach_tag_idempotence(db_session: AsyncSession) -> None:
    """Проверяет идемпотентность attach/detach связи task-tag на уровне репозитория."""
    user = await user_repo.create_user(
        db_session,
        email=f"tag-owner-{uuid4().hex[:8]}@example.com",
        hashed_password="hashed",
    )
    task = await task_repo.create_task(db_session, user, title="Task for tag")
    tag = await tag_repo.create_tag(db_session, name="idempotent", color="#FF0000")

    await tag_repo.attach_tag_to_task(db_session, task, tag)
    await tag_repo.attach_tag_to_task(db_session, task, tag)

    rows = await db_session.execute(
        select(task_tags.c.task_id, task_tags.c.tag_id).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    assert len(rows.all()) == 1

    await tag_repo.detach_tag_from_task(db_session, task, tag)
    await tag_repo.detach_tag_from_task(db_session, task, tag)

    rows_after = await db_session.execute(
        select(task_tags.c.task_id, task_tags.c.tag_id).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    assert rows_after.first() is None
