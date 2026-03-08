from typing import Awaitable, cast

from fastapi import HTTPException, status
from redis.asyncio import Redis

# Атомарный инкремент с установкой TTL через Lua.
# INCR и EXPIRE как два отдельных вызова не атомарны:
# если процесс упадёт между ними - ключ останется без TTL навсегда.
# защита от брутфорса на 2 линии обороны в time_cost=3 у argon2
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def enforce_rate_limit(
    redis: Redis,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Проверяет лимит запросов для ключа. Поднимает 429 с Retry-After при превышении."""
    current = int(
        await cast(
            Awaitable[int], redis.eval(_RATE_LIMIT_SCRIPT, 1, key, window_seconds)
        )
    )

    if current > limit:
        retry_after = await redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много запросов. Повторите через {retry_after} сек.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
