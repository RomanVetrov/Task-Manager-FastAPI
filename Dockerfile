ARG UV_VERSION=0.10.4

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_PROGRESS=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY --from=uvbin /uv /usr/local/bin/uv

# Dependency layer: changes only when lockfile/project metadata changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    WEB_CONCURRENCY=4

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

# Copy prebuilt virtual environment from builder stage.
COPY --from=builder /opt/venv /opt/venv

# Application code and migration files.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
