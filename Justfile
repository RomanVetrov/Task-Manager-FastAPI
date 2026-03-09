set dotenv-load := true

# Показать список доступных команд.
default:
  @just --list

# Поднять все сервисы в фоне с пересборкой образов.
up:
  docker compose up -d --build

# Поднять сервисы в фоне без пересборки.
up-no-build:
  docker compose up -d

# Остановить и удалить контейнеры/сеть (данные в volume сохраняются).
down:
  docker compose down

# Остановить и удалить контейнеры/сеть вместе с volume.
down-v:
  docker compose down -v

# Перезапустить контейнеры без пересборки.
restart:
  docker compose restart

# Показать статус контейнеров.
ps:
  docker compose ps

# Показать полезные ссылки локального окружения.
urls:
  @echo "API docs:   http://localhost:8000/docs"
  @echo "Metrics:    http://localhost:8000/metrics"
  @echo "Prometheus: http://localhost:9090"
  @echo "Grafana:    http://localhost:3000"
  @echo "Jaeger:     http://localhost:16686"
  @echo "Locust UI:  http://localhost:8089"

# Смотреть логи (все сервисы или один сервис: `just logs api`).
logs service="":
  if [ -n "{{service}}" ]; then docker compose logs -f --tail=200 "{{service}}"; else docker compose logs -f --tail=200; fi

# Применить миграции Alembic до последней ревизии.
migrate:
  docker compose run --rm --entrypoint alembic api upgrade head

# Открыть shell внутри контейнера API.
app-shell:
  docker compose exec api sh

# Открыть psql в контейнере Postgres.
db-shell:
  docker compose exec postgres psql -U "${POSTGRES_USER:-task_user}" -d "${POSTGRES_DB:-task_manager}"

# Открыть redis-cli в контейнере Redis.
redis-cli:
  docker compose exec redis redis-cli

# Запустить Locust в UI режиме для ручного управления нагрузкой.
load:
  uv run locust -f load/locustfile.py --host "${LOCUST_HOST:-http://localhost:8000}" --web-port "${LOCUST_WEB_PORT:-8089}"

# Запустить Locust в headless режиме.
load-headless users="20" spawn="2" run_time="5m":
  uv run locust -f load/locustfile.py --host "${LOCUST_HOST:-http://localhost:8000}" --headless -u {{users}} -r {{spawn}} --run-time {{run_time}} --only-summary

# Установить git pre-commit hook в локальный репозиторий.
pre-commit-install:
  uv run pre-commit install

# Прогнать pre-commit проверки по всем файлам.
pre-commit-run:
  uv run pre-commit run --all-files

# Обновить версии хуков в .pre-commit-config.yaml.
pre-commit-update:
  uv run pre-commit autoupdate

# Запустить все тесты.
test:
  uv run pytest

# Запустить только unit-тесты.
test-unit:
  uv run pytest tests/unit -q

# Запустить тесты с покрытием в консоли.
test-cov:
  uv run pytest --cov=app --cov-report=term-missing

# Запустить тесты с HTML-отчётом покрытия (htmlcov/index.html).
test-cov-html:
  uv run pytest --cov=app --cov-report=html

# Проверить код линтером Ruff (без автоисправлений).
lint:
  uv run ruff check .

# Проверить код Ruff и автоматически применить безопасные фиксы.
lint-fix:
  uv run ruff check . --fix

# Отформатировать код через Ruff formatter.
format:
  uv run ruff format .
