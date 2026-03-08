from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.task import Task

# Связь Task <-> Tag (многие ко многим).
# task_tags определён здесь; Task импортирует его когда понадобится relationship.
task_tags = Table(
    "task_tags",
    Base.metadata,
    Column(
        "task_id",
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(CreatedAtMixin, Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Теги глобальные, имя уникально в системе.
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # Формат #RRGGBB, валидация на уровне схемы Pydantic.
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    tasks: Mapped[list[Task]] = relationship(
        secondary=task_tags,
        back_populates="tags",
    )
