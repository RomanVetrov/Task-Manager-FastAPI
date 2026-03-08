from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.models.task import Task
from app.repositories import tag_repo
from app.schemas.tag import TagCreate, TagUpdate


class TagAlreadyExists(Exception):
    """Тег с таким именем уже существует."""


async def create_tag(session: AsyncSession, payload: TagCreate) -> Tag:
    """Создаёт тег. Поднимает TagAlreadyExists при конфликте имени."""
    if await tag_repo.get_tag_by_name(session, payload.name):
        raise TagAlreadyExists(payload.name)
    return await tag_repo.create_tag(
        session,
        name=payload.name,
        color=payload.color,
    )


async def list_tags(session: AsyncSession) -> Sequence[Tag]:
    """Возвращает список всех тегов."""
    return await tag_repo.list_tags(session)


async def update_tag(session: AsyncSession, tag: Tag, payload: TagUpdate) -> Tag:
    """Обновляет тег. Поднимает TagAlreadyExists при конфликте имени."""
    updates = payload.model_dump(exclude_unset=True)
    new_name = updates.get("name")
    if isinstance(new_name, str) and new_name != tag.name:
        existing = await tag_repo.get_tag_by_name(session, new_name)
        if existing:
            raise TagAlreadyExists(new_name)
    return await tag_repo.update_tag(session, tag, **updates)


async def delete_tag(session: AsyncSession, tag: Tag) -> UUID:
    """Удаляет тег и возвращает его id."""
    return await tag_repo.delete_tag(session, tag)


async def attach_tag_to_task(session: AsyncSession, task: Task, tag: Tag) -> None:
    """Привязывает тег к задаче."""
    await tag_repo.attach_tag_to_task(session, task, tag)


async def detach_tag_from_task(session: AsyncSession, task: Task, tag: Tag) -> None:
    """Отвязывает тег от задачи."""
    await tag_repo.detach_tag_from_task(session, task, tag)
