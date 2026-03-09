from __future__ import annotations

from app.metrics import observe_http_request, render_metrics


def test_observe_http_request_and_render_metrics_contains_custom_series() -> None:
    """Проверяет, что observe_http_request пишет метрики, а render_metrics их экспортирует."""
    observe_http_request(
        method="GET",
        path="/smoke",
        status=200,
        duration_seconds=0.123,
    )

    content, media_type = render_metrics()
    text = content.decode("utf-8")

    assert "http_requests_total" in text
    assert 'path="/smoke"' in text
    assert media_type
