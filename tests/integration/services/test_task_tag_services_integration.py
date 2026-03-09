from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import task_tags
from app.repositories import task_repo
from app.schemas.tag import TagCreate
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import auth as auth_service
from app.services import tag as tag_service
from app.services import task as task_service
from app.services.tag import TagAlreadyExists
from app.services.task import InvalidDueDate

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_task_crud_lifecycle_for_user(db_session: AsyncSession) -> None:
    """Проверяет полный жизненный цикл задачи: create/list/update/delete."""
    user = await auth_service.register_user(
        db_session,
        email="tasks-owner@example.com",
        password="StrongPass123!",
    )

    created = await task_service.create_task(
        db_session,
        user,
        payload=TaskCreate(
            title="Integration Task",
            description="created in integration test",
            due_date=date.today() + timedelta(days=3),
        ),
    )
    assert created.user_id == user.id

    listed = await task_service.get_user_tasks(db_session, user)
    assert len(listed) == 1
    assert listed[0].id == created.id

    updated = await task_service.update_task(
        db_session,
        created,
        payload=TaskUpdate(title="Updated Task"),
    )
    assert updated.title == "Updated Task"

    deleted_id = await task_service.delete_task(db_session, updated)
    assert deleted_id == created.id

    loaded = await task_repo.get_task_by_id(db_session, created.id)
    assert loaded is None


@pytest.mark.asyncio
async def test_task_create_raises_for_past_due_date(db_session: AsyncSession) -> None:
    """Проверяет валидацию дедлайна: задача с прошлой датой не создаётся."""
    user = await auth_service.register_user(
        db_session,
        email="past-due@example.com",
        password="StrongPass123!",
    )

    with pytest.raises(InvalidDueDate):
        await task_service.create_task(
            db_session,
            user,
            payload=TaskCreate(
                title="Invalid due date",
                due_date=date.today() - timedelta(days=1),
            ),
        )


@pytest.mark.asyncio
async def test_tag_unique_name_conflict(db_session: AsyncSession) -> None:
    """Проверяет, что сервис тегов не даёт создать дубликат имени."""
    await tag_service.create_tag(
        db_session,
        payload=TagCreate(name="backend", color="#22AAFF"),
    )

    with pytest.raises(TagAlreadyExists):
        await tag_service.create_tag(
            db_session,
            payload=TagCreate(name="backend", color="#112233"),
        )


@pytest.mark.asyncio
async def test_attach_and_detach_tag_to_task(db_session: AsyncSession) -> None:
    """Проверяет идемпотентную привязку/отвязку тега к задаче через таблицу связей."""
    user = await auth_service.register_user(
        db_session,
        email="attach-owner@example.com",
        password="StrongPass123!",
    )
    task = await task_service.create_task(
        db_session,
        user,
        payload=TaskCreate(title="Task for tags"),
    )
    tag = await tag_service.create_tag(
        db_session,
        payload=TagCreate(name="urgent", color="#FF0000"),
    )

    await tag_service.attach_tag_to_task(db_session, task, tag)
    await tag_service.attach_tag_to_task(db_session, task, tag)

    linked_rows = await db_session.execute(
        select(task_tags.c.task_id, task_tags.c.tag_id).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    assert len(linked_rows.all()) == 1

    await tag_service.detach_tag_from_task(db_session, task, tag)
    await tag_service.detach_tag_from_task(db_session, task, tag)

    after_detach = await db_session.execute(
        select(task_tags.c.task_id, task_tags.c.tag_id).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    assert after_detach.first() is None
