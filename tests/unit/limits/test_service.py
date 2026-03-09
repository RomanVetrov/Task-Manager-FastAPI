from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from redis.asyncio import Redis

from app.limits.service import enforce_rate_limit


@pytest.fixture
def fake_redis() -> Redis:
    """Создаёт фейковый Redis-клиент для проверки логики rate limit."""
    redis = cast(Redis, AsyncMock(spec=Redis))
    redis.eval = AsyncMock()
    redis.ttl = AsyncMock()
    return redis


@pytest.mark.asyncio
async def test_enforce_rate_limit_allows_requests_within_limit(
    fake_redis: Redis,
) -> None:
    """Проверяет, что при current <= limit функция не выбрасывает исключение."""
    cast(AsyncMock, fake_redis.eval).return_value = 5

    await enforce_rate_limit(
        fake_redis,
        key="rl:test:ip:127.0.0.1",
        limit=5,
        window_seconds=60,
    )

    cast(AsyncMock, fake_redis.ttl).assert_not_awaited()


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_429_with_retry_after(
    fake_redis: Redis,
) -> None:
    """Проверяет, что превышение лимита даёт 429 и корректный Retry-After."""
    cast(AsyncMock, fake_redis.eval).return_value = 11
    cast(AsyncMock, fake_redis.ttl).return_value = 15

    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit(
            fake_redis,
            key="rl:test:ip:127.0.0.1",
            limit=10,
            window_seconds=60,
        )

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "15"}
    assert "15 сек." in exc.value.detail


@pytest.mark.asyncio
async def test_enforce_rate_limit_fallbacks_retry_after_to_one(
    fake_redis: Redis,
) -> None:
    """Проверяет fallback Retry-After=1, если Redis вернул TTL <= 0."""
    cast(AsyncMock, fake_redis.eval).return_value = 3
    cast(AsyncMock, fake_redis.ttl).return_value = 0

    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit(
            fake_redis,
            key="rl:test:ip:127.0.0.1",
            limit=2,
            window_seconds=60,
        )

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "1"}
