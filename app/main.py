from contextlib import asynccontextmanager
from typing import Awaitable, cast

from fastapi import FastAPI

from app.logging_config import setup_logging
from app.middleware import LoggingMiddleware, MetricsMiddleware, RequestIDMiddleware
from app.redis import redis_client
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.tags import router as tags_router
from app.routes.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cast(Awaitable[bool], redis_client.ping())
    try:
        yield
    finally:
        await redis_client.aclose()


setup_logging()

app = FastAPI(
    title="Task Manager API",
    description="API для управления задачами с авторизацией",
    version="0.1.0",
    lifespan=lifespan,
)

# middleware регистрируются в обратном порядке (луковица).
# RequestID должен сработать первым, поэтому добавляем его последним.
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(metrics_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(tags_router, prefix="/api/v1")
