from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)

TASKS_CACHE_HITS_TOTAL = Counter(
    "tasks_cache_hits_total",
    "Количество попаданий в кэш списка задач.",
)

TASKS_CACHE_MISSES_TOTAL = Counter(
    "tasks_cache_misses_total",
    "Количество промахов кэша списка задач.",
)


def observe_http_request(
    *,
    method: str,
    path: str,
    status: int,
    duration_seconds: float,
) -> None:
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(
        duration_seconds
    )


def observe_tasks_cache_hit() -> None:
    """Регистрирует попадание в кэш списка задач."""
    TASKS_CACHE_HITS_TOTAL.inc()


def observe_tasks_cache_miss() -> None:
    """Регистрирует промах кэша списка задач."""
    TASKS_CACHE_MISSES_TOTAL.inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
