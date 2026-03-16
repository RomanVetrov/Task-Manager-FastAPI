"""API-тесты для readiness endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_readiness_200_when_both_ok(client: AsyncClient) -> None:
    """GET /health/ready возвращает 200 и ok для db и redis."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


async def test_readiness_503_when_redis_down(client: AsyncClient, fake_redis) -> None:
    """GET /health/ready возвращает 503, когда Redis недоступен."""
    fake_redis.raise_on_ping = True
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["db"] == "ok"
    assert body["redis"] == "down"
