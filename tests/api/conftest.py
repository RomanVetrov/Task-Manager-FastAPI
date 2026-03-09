from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.models.user import User
from app.redis import get_redis
from app.routes.auth import router as auth_router
from app.routes.tags import router as tags_router
from app.routes.tasks import router as tasks_router
from app.security.dependences import get_current_user


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.eval_result = 1
        self.ttl_result = 60
        self.forced_delete_result: int | None = None
        self.set_calls: list[tuple[str, str, int]] = []
        self.delete_calls: list[str] = []

    async def eval(
        self, script: str, number_of_keys: int, key: str, window_seconds: int
    ) -> int:
        _ = (script, number_of_keys, key, window_seconds)
        return self.eval_result

    async def ttl(self, key: str) -> int:
        _ = key
        return self.ttl_result

    async def set(self, key: str, value: str, ex: int) -> bool:
        self.store[key] = value
        self.set_calls.append((key, value, ex))
        return True

    async def delete(self, key: str) -> int:
        self.delete_calls.append(key)
        if self.forced_delete_result is not None:
            if self.forced_delete_result == 1:
                self.store.pop(key, None)
            return self.forced_delete_result

        existed = key in self.store
        self.store.pop(key, None)
        return 1 if existed else 0


@pytest.fixture
def fake_session() -> object:
    return object()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def current_user() -> User:
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
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
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
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
