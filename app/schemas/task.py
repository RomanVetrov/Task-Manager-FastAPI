from __future__ import annotations

from datetime import date, datetime
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
