from __future__ import annotations

from pydantic import BaseModel

from app.schemas.tag import TagRead
from app.schemas.task import TaskRead


class TaskCountsByStatus(BaseModel):
    """Количество задач пользователя по статусам."""

    todo: int = 0
    in_progress: int = 0
    done: int = 0


class DashboardRead(BaseModel):
    """Данные дашборда: последние задачи, все теги, счётчики по статусам."""

    tasks: list[TaskRead]
    tags: list[TagRead]
    counts_by_status: TaskCountsByStatus
