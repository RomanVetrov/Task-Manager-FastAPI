from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.orm import Mapped, mapped_column


UTC_NOW = text("timezone('utc', now())")  # всегда UTC на стороне БД


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=UTC_NOW,
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=UTC_NOW,
        server_onupdate=UTC_NOW,
        nullable=False,
    )
