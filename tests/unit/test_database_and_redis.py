from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis, redis_client


@pytest.mark.asyncio
async def test_get_db_yields_async_session() -> None:
    """Проверяет, что get_db отдаёт AsyncSession и корректно закрывается."""
    generator = get_db()
    session = await anext(generator)

    assert isinstance(session, AsyncSession)

    await generator.aclose()


@pytest.mark.asyncio
async def test_get_redis_returns_shared_client() -> None:
    """Проверяет, что get_redis возвращает общий redis_client из модуля."""
    client = await get_redis()

    assert client is redis_client
