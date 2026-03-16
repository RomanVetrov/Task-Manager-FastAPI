from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.routes.health import (
    _check_db,
    _check_redis,
    db_health,
    readiness,
    redis_health,
)


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


@pytest.mark.asyncio
async def test_check_db_returns_down_on_exception(fake_session: AsyncSession) -> None:
    """_check_db возвращает db=down при исключении."""
    cast(AsyncMock, fake_session.execute).side_effect = Exception("connection lost")
    result = await _check_db(fake_session)
    assert result == {"db": "down"}


@pytest.mark.asyncio
async def test_check_redis_returns_down_on_exception(fake_redis: Redis) -> None:
    """_check_redis возвращает redis=down при исключении."""
    cast(AsyncMock, fake_redis.ping).side_effect = Exception("connection refused")
    result = await _check_redis(fake_redis)
    assert result == {"redis": "down"}


@pytest.mark.asyncio
async def test_readiness_200_when_both_ok(
    fake_redis: Redis, fake_session: AsyncSession
) -> None:
    """Readiness возвращает 200 и ok для db и redis, когда оба источника доступны."""
    cast(AsyncMock, fake_redis.ping).return_value = True
    response = Response()
    result = await readiness(redis=fake_redis, session=fake_session, response=response)
    assert result == {"db": "ok", "redis": "ok"}
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_readiness_503_when_db_down(
    fake_redis: Redis, fake_session: AsyncSession
) -> None:
    """Readiness возвращает 503, когда БД недоступна."""
    cast(AsyncMock, fake_redis.ping).return_value = True
    cast(AsyncMock, fake_session.execute).side_effect = Exception("db down")
    response = Response()
    result = await readiness(redis=fake_redis, session=fake_session, response=response)
    assert result == {"db": "down", "redis": "ok"}
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_readiness_503_when_redis_down(
    fake_redis: Redis, fake_session: AsyncSession
) -> None:
    """Readiness возвращает 503, когда Redis недоступен."""
    cast(AsyncMock, fake_redis.ping).side_effect = Exception("redis down")
    response = Response()
    result = await readiness(redis=fake_redis, session=fake_session, response=response)
    assert result == {"db": "ok", "redis": "down"}
    assert response.status_code == 503
