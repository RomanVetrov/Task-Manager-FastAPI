from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.database import get_db
from app.models.user import User
from app.redis import get_redis
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.health import router as health_router
from app.routes.tags import router as tags_router
from app.routes.tasks import router as tasks_router
from app.security.dependences import get_current_user


class FakeRedis:
    """Тестовая реализация Redis-клиента для API-тестов."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.eval_result = 1
        self.ttl_result = 60
        self.forced_delete_result: int | None = None
        self.set_calls: list[tuple[str, str, int]] = []
        self.delete_calls: list[str] = []
        self.raise_on_get = False
        self.raise_on_set = False
        self.raise_on_delete = False
        self.raise_on_ping = False

    async def ping(self) -> bool:
        """Эмуляция Redis PING для health-check."""
        if self.raise_on_ping:
            raise RedisConnectionError("Ошибка соединения с Redis")
        return True

    async def eval(
        self, script: str, number_of_keys: int, key: str, window_seconds: int
    ) -> int:
        """Возвращает заранее заданный результат выполнения Lua-скрипта."""
        _ = (script, number_of_keys, key, window_seconds)
        return self.eval_result

    async def ttl(self, key: str) -> int:
        """Возвращает заранее заданный TTL."""
        _ = key
        return self.ttl_result

    async def set(self, key: str, value: str, ex: int) -> bool:
        """Сохраняет значение по ключу с TTL."""
        if self.raise_on_set:
            raise RedisConnectionError("Ошибка записи в тестовый Redis")
        self.store[key] = value
        self.set_calls.append((key, value, ex))
        return True

    async def get(self, key: str) -> str | None:
        """Возвращает значение по ключу."""
        if self.raise_on_get:
            raise RedisConnectionError("Ошибка чтения из тестового Redis")
        return self.store.get(key)

    async def scan_iter(self, match: str):
        """Итерирует ключи по паттерну, как Redis SCAN."""
        if match.endswith("*"):
            prefix = match[:-1]
            for key in list(self.store.keys()):
                if key.startswith(prefix):
                    yield key
            return
        if match in self.store:
            yield match

    async def delete(self, *keys: str) -> int:
        """Удаляет один или несколько ключей и возвращает число удалённых."""
        if self.raise_on_delete:
            raise RedisConnectionError("Ошибка удаления из тестового Redis")
        self.delete_calls.extend(keys)
        if self.forced_delete_result is not None:
            if self.forced_delete_result == 1:
                for key in keys:
                    self.store.pop(key, None)
            return self.forced_delete_result

        removed = 0
        for key in keys:
            existed = key in self.store
            self.store.pop(key, None)
            removed += 1 if existed else 0
        return removed


@pytest.fixture
def fake_session() -> object:
    """Возвращает объект-заглушку сессии для API-тестов (с execute для health)."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def fake_redis() -> FakeRedis:
    """Создаёт тестовый Redis-клиент."""
    return FakeRedis()


@pytest.fixture
def current_user() -> User:
    """Возвращает тестового текущего пользователя."""
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            email="current@example.com",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.now(UTC),
        ),
    )


@pytest.fixture
def api_app(fake_session: object, fake_redis: FakeRedis, current_user: User) -> FastAPI:
    """Собирает тестовое FastAPI-приложение с override зависимостей."""
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(tags_router, prefix="/api/v1")

    async def override_db() -> AsyncIterator[object]:
        yield fake_session

    async def override_redis() -> FakeRedis:
        return fake_redis

    async def override_current_user() -> User:
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest_asyncio.fixture
async def client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Предоставляет асинхронный HTTP-клиент для API-тестов."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
