from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.routes.health import db_health, redis_health


@pytest.fixture
def fake_redis() -> Redis:
    """Создаёт фейковый Redis для smoke-тестов health-роута."""
    redis = cast(Redis, AsyncMock(spec=Redis))
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def fake_session() -> AsyncSession:
    """Создаёт фейковую AsyncSession для smoke-тестов health-роута."""
    session = cast(AsyncSession, AsyncMock(spec=AsyncSession))
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_redis_health_reports_ok(fake_redis: Redis) -> None:
    """Проверяет, что /health/redis возвращает ok, когда Redis отвечает True."""
    cast(AsyncMock, fake_redis.ping).return_value = True

    result = await redis_health(redis=fake_redis)

    assert result == {"redis": "ok"}


@pytest.mark.asyncio
async def test_redis_health_reports_down(fake_redis: Redis) -> None:
    """Проверяет, что /health/redis возвращает down, когда Redis отвечает False."""
    cast(AsyncMock, fake_redis.ping).return_value = False

    result = await redis_health(redis=fake_redis)

    assert result == {"redis": "down"}


@pytest.mark.asyncio
async def test_db_health_executes_ping_query(fake_session: AsyncSession) -> None:
    """Проверяет, что /health/db выполняет SELECT 1 и возвращает ok."""
    result = await db_health(session=fake_session)

    assert result == {"db": "ok"}
    cast(AsyncMock, fake_session.execute).assert_awaited_once()
