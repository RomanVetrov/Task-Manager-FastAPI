# Task Manager FastAPI

[![CI](https://github.com/RomanVetrov/Task-Manager-FastAPI/actions/workflows/ci.yml/badge.svg)](https://github.com/RomanVetrov/Task-Manager-FastAPI/actions/workflows/ci.yml)
[![CD](https://github.com/RomanVetrov/Task-Manager-FastAPI/actions/workflows/cd.yml/badge.svg)](https://github.com/RomanVetrov/Task-Manager-FastAPI/actions/workflows/cd.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6522C?logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?logo=grafana&logoColor=white)](https://grafana.com/)
[![Jaeger](https://img.shields.io/badge/Jaeger-Tracing-66CFE3)](https://www.jaegertracing.io/)
[![Ruff](https://img.shields.io/badge/Ruff-Lint%2FFormat-D7FF64)](https://docs.astral.sh/ruff/)
[![Pytest](https://img.shields.io/badge/Pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

Практический backend-проект на FastAPI с акцентом на:
- безопасную auth-логику (JWT access + refresh, Argon2, rate limit)
- чистую слоистую архитектуру (routes/services/repositories/models)
- полноценную наблюдаемость (logs + metrics + tracing)
- production-ready инфраструктуру (Docker, CI/CD, GHCR)

## Что реализовано

- Регистрация, логин, refresh, logout, endpoint `/me`
- CRUD задач с валидацией дедлайна и ownership-check
- CRUD тегов и связь many-to-many `Task <-> Tag`
- Ограничение запросов по IP для auth-ручек через Redis Lua script
- Корреляция запросов через `X-Request-ID`
- Структурированные JSON-логи с `trace_id` и `span_id`
- Метрики Prometheus и готовый Grafana dashboard
- Трейсинг FastAPI + SQLAlchemy + Redis в Jaeger
- Нагрузочные сценарии в Locust
- Unit / API / Integration тесты, coverage, pre-commit, Ruff

## Технологический стек

| Слой | Инструменты |
|---|---|
| API | FastAPI, Pydantic |
| Бизнес-логика | Services, Repositories |
| БД | PostgreSQL, SQLAlchemy 2.0 (async), Alembic |
| Кэш / лимиты | Redis |
| Безопасность | JWT (access/refresh), Argon2, rate limiting |
| Observability | Structlog, Prometheus, Grafana, OpenTelemetry, Jaeger |
| Тесты | Pytest, pytest-asyncio, httpx, pytest-cov |
| Инфраструктура | Docker, Docker Compose, GitHub Actions, GHCR |
| Инструменты | uv, Ruff, pre-commit, Just |

## Архитектура и маппинг

### Доменные сущности

- `User` -> `Task` = `1:N`
- `Task` -> `Tag` = `N:M` через `task_tags`

### Слои

- `app/routes`
  HTTP-слой: валидация входа/выхода, статус-коды, DI
- `app/services`
  Бизнес-правила: auth-flow, проверка активного пользователя, логика задач/тегов
- `app/repositories`
  Изоляция SQL-запросов
- `app/models` + `app/schemas`
  SQLAlchemy-модели и Pydantic-контракты
- `app/security`, `app/limits`
  JWT, password hashing, refresh guard, rate limit
- `app/middleware`, `app/metrics`, `app/telemetry`
  Логирование, метрики, трейсинг

## API маппинг

Префикс API: `/api/v1`

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

### Tasks

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}`
- `DELETE /tasks/{task_id}`
- `POST /tasks/{task_id}/tags/{tag_id}`
- `DELETE /tasks/{task_id}/tags/{tag_id}`

### Tags

- `POST /tags`
- `GET /tags`
- `GET /tags/{tag_id}`
- `PATCH /tags/{tag_id}`
- `DELETE /tags/{tag_id}`

### Service endpoints

- `GET /metrics`
- `GET /api/v1/health/db`
- `GET /api/v1/health/redis`

## Локальный запуск через Docker Compose

### 1. Подготовить `.env`

Минимально нужны:

```env
POSTGRES_PASSWORD=your_strong_password
SECRET_KEY=your_secret_key_min_32_chars
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

### 2. Поднять сервисы

```bash
just up
```

### 3. Открыть сервисы

```bash
just urls
```

Ожидаемые адреса:

- API docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Jaeger: `http://localhost:16686`
- Locust: `http://localhost:8089`

## Запуск без Docker (режим разработки)

```bash
uv sync --frozen --dev
uv run uvicorn app.main:app --reload
```

Важно: для полного функционала нужны PostgreSQL и Redis.

## Наблюдаемость

### Logs

- middleware пишет JSON-логи запроса/ответа
- каждый запрос получает `X-Request-ID`
- в лог автоматически добавляются `trace_id` и `span_id`

### Metrics

- endpoint: `GET /metrics`
- базовые метрики:
  - `http_requests_total`
  - `http_request_duration_seconds`

### Tracing

- OpenTelemetry включен по умолчанию
- экспорт в Jaeger по OTLP (`4317`)
- есть спаны для auth/jwt/password операций и инфраструктурных вызовов

## Нагрузочное тестирование

Locust-сценарии находятся в `load/locustfile.py`.

Запуск UI-режима:

```bash
just load
```

Headless-режим:

```bash
just load-headless users=100 spawn=10 run_time=10m
```

## Тесты и качество кода

Основные команды:

```bash
just test
just test-unit
just test-integration
just test-cov
just lint
just format
```

Pre-commit:

```bash
just pre-commit-install
just pre-commit-run
```

## CI/CD

### CI (`.github/workflows/ci.yml`)

На каждый `push` и `pull_request` в `main`:
- Ruff lint + format check
- тесты с coverage и JUnit artifact
- проверка Docker build

### CD (`.github/workflows/cd.yml`)

Триггеры:
- тег формата `v*.*.*`
- ручной запуск (`workflow_dispatch`)

Результат:
- сборка и публикация Docker image в GHCR

## Релизный поток

1. Пуш в `main` и зеленый CI
2. Создание тега версии
3. Публикация image в GHCR через CD

Пример:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## GHCR package

После релиза образ доступен в GitHub Packages репозитория.
Пример pull:

```bash
docker pull ghcr.io/romanvetrov/task-manager-fastapi:v0.1.0
```

## Структура проекта

```text
app/
  routes/         # HTTP endpoints
  services/       # бизнес-логика
  repositories/   # работа с БД
  models/         # SQLAlchemy модели
  schemas/        # Pydantic схемы
  security/       # JWT, password, auth dependencies
  limits/         # rate-limit зависимости и сервис
  middleware.py   # request id, logging, metrics
  telemetry.py    # OpenTelemetry setup
tests/
  unit/
  api/
  integration/
monitoring/
  prometheus.yml
  grafana/
load/
  locustfile.py
```

## Что дальше

- SonarCloud quality gate
- финальная полировка README примерами API-ответов
- разворот CD в отдельную deployment-среду
