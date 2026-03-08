from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, task_tags
from app.models.task import Task


async def get_tag_by_id(session: AsyncSession, tag_id: UUID) -> Tag | None:
    """Возвращает тег по id или None."""
    return await session.get(Tag, tag_id)


async def get_tag_by_name(session: AsyncSession, name: str) -> Tag | None:
    """Возвращает тег по имени или None."""
    result = await session.execute(select(Tag).where(Tag.name == name))
    return result.scalar_one_or_none()


async def list_tags(session: AsyncSession) -> Sequence[Tag]:
    """Возвращает список тегов по имени."""
    result = await session.execute(select(Tag).order_by(Tag.name.asc()))
    return result.scalars().all()


async def create_tag(session: AsyncSession, *, name: str, color: str) -> Tag:
    """Создаёт и сохраняет тег."""
    tag = Tag(name=name, color=color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return tag


async def update_tag(session: AsyncSession, tag: Tag, **data: Any) -> Tag:
    """Обновляет переданные поля тега."""
    for field, value in data.items():
        setattr(tag, field, value)
    await session.commit()
    await session.refresh(tag)
    return tag


async def delete_tag(session: AsyncSession, tag: Tag) -> UUID:
    """Удаляет тег и возвращает его id."""
    tag_id = tag.id
    await session.delete(tag)
    await session.commit()
    return tag_id


async def attach_tag_to_task(session: AsyncSession, task: Task, tag: Tag) -> None:
    """Привязывает тег к задаче (идемпотентно)."""
    exists_result = await session.execute(
        select(task_tags.c.task_id).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    if exists_result.first():
        return

    await session.execute(insert(task_tags).values(task_id=task.id, tag_id=tag.id))
    await session.commit()


async def detach_tag_from_task(session: AsyncSession, task: Task, tag: Tag) -> None:
    """Отвязывает тег от задачи (идемпотентно)."""
    await session.execute(
        delete(task_tags).where(
            task_tags.c.task_id == task.id,
            task_tags.c.tag_id == tag.id,
        )
    )
    await session.commit()
