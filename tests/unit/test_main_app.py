from __future__ import annotations

from app.main import API_V1_PREFIX, app
from app.middleware import LoggingMiddleware, MetricsMiddleware, RequestIDMiddleware


def test_main_registers_expected_routes_with_api_prefix() -> None:
    """Проверяет, что роутеры подключены с корректным префиксом API v1."""
    paths = {route.path for route in app.routes}

    assert "/metrics" in paths
    assert f"{API_V1_PREFIX}/auth/login" in paths
    assert f"{API_V1_PREFIX}/health/db" in paths
    assert f"{API_V1_PREFIX}/tasks" in paths
    assert f"{API_V1_PREFIX}/tags" in paths


def test_main_registers_expected_middlewares() -> None:
    """Проверяет, что middleware стека зарегистрированы в приложении."""
    middleware_classes = {middleware.cls for middleware in app.user_middleware}

    assert RequestIDMiddleware in middleware_classes
    assert LoggingMiddleware in middleware_classes
    assert MetricsMiddleware in middleware_classes
