import asyncio
from typing import Annotated, Awaitable, cast

from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis

router = APIRouter(prefix="/health", tags=["health"])
RedisClient = Annotated[Redis, Depends(get_redis)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/redis")
async def redis_health(redis: RedisClient) -> dict[str, str]:
    ok = await cast(Awaitable[bool], redis.ping())
    return {"redis": "ok" if ok else "down"}


@router.get("/db")
async def db_health(session: DbSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"db": "ok"}


@router.get("/ready")
async def readiness(
    redis: RedisClient, session: DbSession, response: Response
) -> dict[str, str]:
    """Проверка готовности: БД и Redis параллельно. Время ответа ≈ max(db, redis)."""
    db_result, redis_result = await asyncio.gather(
        _check_db(session),
        _check_redis(redis),
    )
    status_db, status_redis = db_result["db"], redis_result["redis"]
    if status_db == "ok" and status_redis == "ok":
        response.status_code = 200
    else:
        response.status_code = 503
    return {"db": status_db, "redis": status_redis}


async def _check_db(session: DbSession) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception:
        return {"db": "down"}


async def _check_redis(redis: RedisClient) -> dict[str, str]:
    try:
        ok = await cast(Awaitable[bool], redis.ping())
        return {"redis": "ok" if ok else "down"}
    except Exception:
        return {"redis": "down"}
