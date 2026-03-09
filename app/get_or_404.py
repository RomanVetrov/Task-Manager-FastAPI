from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tag import Tag
from app.models.task import Task
from app.models.user import User
from app.repositories import tag_repo, task_repo
from app.security.dependences import get_current_user


async def get_task_or_404(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    """Возвращает задачу по id. 404 если не найдена, 403 если чужая."""
    task = await task_repo.get_task_by_id(session, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
        )
    if task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return task


async def get_tag_or_404(
    tag_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Tag:
    """Возвращает тег по id или 404 если не найден."""
    tag = await tag_repo.get_tag_by_id(session, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Тег не найден"
        )
    return tag


TagDep = Annotated[Tag, Depends(get_tag_or_404)]
CurrentUser = Annotated[User, Depends(get_current_user)]
TaskDep = Annotated[Task, Depends(get_task_or_404)]
