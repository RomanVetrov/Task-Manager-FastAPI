from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import PriorityEnum, StatusEnum


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    status: StatusEnum = StatusEnum.todo
    priority: PriorityEnum = PriorityEnum.medium
    due_date: date | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    status: StatusEnum | None = None
    priority: PriorityEnum | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: StatusEnum
    priority: PriorityEnum
    due_date: date | None
    user_id: UUID
    created_at: datetime


class TaskDeleted(BaseModel):
    id: UUID


class TaskSortBy(str, Enum):
    created_at = "created_at"
    due_date = "due_date"
    task_title = "title"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class TaskListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusEnum | None = None
    priority: PriorityEnum | None = None
    q: str | None = Field(default=None, min_length=1, max_length=255)
    due_before: date | None = None
    due_after: date | None = None
    sort_by: TaskSortBy = TaskSortBy.created_at
    sort_order: SortOrder = SortOrder.desc
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
