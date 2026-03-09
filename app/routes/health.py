from typing import Annotated, Awaitable, cast

from fastapi import APIRouter, Depends
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
