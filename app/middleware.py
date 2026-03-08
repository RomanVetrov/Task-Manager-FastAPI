import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import observe_http_request

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Присваивает каждому запросу уникальный ID и возвращает его в заголовке ответа."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # берём из заголовка если клиент прислал свой, иначе генерируем
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # кладём в state чтобы было доступно из роутов
        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый входящий запрос и ответ с временем выполнения."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # request_id уже есть в state, RequestIDMiddleware отработал раньше
        request_id = getattr(request.state, "request_id", "-")
        start_time = time.perf_counter()

        await logger.ainfo(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000)

        await logger.ainfo(
            "response",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Собирает базовые HTTP-метрики для Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Не учитываем self-scrape endpoint, чтобы не шуметь метриками.
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            observe_http_request(
                method=request.method,
                path=route_path,
                status=status_code,
                duration_seconds=time.perf_counter() - start_time,
            )
