from __future__ import annotations

import uuid
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.tag import Tag


class StatusEnum(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Task(CreatedAtMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[StatusEnum] = mapped_column(
        String(20), nullable=False, default=StatusEnum.todo
    )
    priority: Mapped[PriorityEnum] = mapped_column(
        String(10), nullable=False, default=PriorityEnum.medium
    )
    due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="task_tags",
        back_populates="tasks",
    )
