from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_or_404 import CurrentUser
from app.repositories import task_repo
from app.schemas.dashboard import DashboardRead, TaskCountsByStatus
from app.schemas.tag import TagRead
from app.schemas.task import TaskListFilters, TaskRead
from app.services import tag as tag_service
from app.services import task as task_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Ограниченный набор задач для дашборда (последние по дате создания).
_DASHBOARD_TASK_LIMIT = 10


@router.get("", summary="Дашборд: задачи, теги и счётчики по статусам")
async def get_dashboard(
    current_user: CurrentUser,
    session: DbSession,
) -> DashboardRead:
    """Возвращает задачи (с лимитом), теги и счётчики задач по статусам.
    Три независимых чтения выполняются параллельно (asyncio.gather).
    """
    filters = TaskListFilters(limit=_DASHBOARD_TASK_LIMIT, offset=0)
    tasks_result, tags_result, counts_result = await asyncio.gather(
        task_service.get_user_tasks(session, current_user, filters),
        tag_service.list_tags(session),
        task_repo.get_task_counts_by_status(session, current_user),
    )
    return DashboardRead(
        tasks=[TaskRead.model_validate(t) for t in tasks_result],
        tags=[TagRead.model_validate(t) for t in tags_result],
        counts_by_status=TaskCountsByStatus(**counts_result),
    )
