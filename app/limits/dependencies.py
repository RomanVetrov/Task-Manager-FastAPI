from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.limits.service import enforce_rate_limit
from app.redis import get_redis


def rate_limit_by_ip(limit: int, window_seconds: int, scope: str) -> Callable:
    """Фабрика зависимости: ограничивает запросы по IP для заданного scope."""

    async def dependency(
        request: Request,
        redis: Annotated[Redis, Depends(get_redis)],
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{scope}:ip:{client_ip}"
        await enforce_rate_limit(
            redis,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency
