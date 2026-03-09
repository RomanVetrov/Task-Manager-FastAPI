from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.routes import metrics as metrics_route


@pytest.mark.asyncio
async def test_metrics_route_returns_response_from_render_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что /metrics возвращает body и media_type, полученные из render_metrics."""
    render_metrics = Mock(
        return_value=(b"# test metrics\n", "text/plain; version=0.0.4")
    )
    monkeypatch.setattr(metrics_route, "render_metrics", render_metrics)

    response = await metrics_route.metrics()

    assert response.body == b"# test metrics\n"
    assert response.media_type == "text/plain; version=0.0.4"
