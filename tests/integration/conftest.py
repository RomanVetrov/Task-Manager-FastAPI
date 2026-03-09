from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base

_DUMMY_DB_URL = "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"


def _integration_db_url() -> str:
    explicit = os.getenv("INTEGRATION_DATABASE_URL")
    if explicit:
        return explicit

    env_db_url = os.getenv("DATABASE_URL")
    if env_db_url and env_db_url != _DUMMY_DB_URL:
        return env_db_url

    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()

    return settings.DATABASE_URL


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    # Важно: импорт моделей регистрирует таблицы в Base.metadata.
    import app.models.tag  # noqa: F401
    import app.models.task  # noqa: F401
    import app.models.user  # noqa: F401

    db_url = _integration_db_url()
    schema = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(db_url, echo=False)
    test_engine = None
    schema_created = False

    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True

        test_engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"server_settings": {"search_path": schema}},
        )
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            yield session
    except Exception as exc:
        pytest.skip(f"Интеграционная БД недоступна: {exc}")
    finally:
        if test_engine is not None:
            await test_engine.dispose()
        if schema_created:
            try:
                async with admin_engine.begin() as conn:
                    await conn.execute(
                        text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                    )
            except Exception:
                pass
        await admin_engine.dispose()
