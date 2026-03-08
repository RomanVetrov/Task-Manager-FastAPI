from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=HEX_COLOR_PATTERN)


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=50)
    color: str | None = Field(None, pattern=HEX_COLOR_PATTERN)


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str
    created_at: datetime


class TagDeleted(BaseModel):
    id: UUID


class TaskTagLink(BaseModel):
    task_id: UUID
    tag_id: UUID
