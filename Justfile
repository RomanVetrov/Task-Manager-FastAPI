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

# Проверить код линтером Ruff (без автоисправлений).
lint:
  uv run ruff check .

# Проверить код Ruff и автоматически применить безопасные фиксы.
lint-fix:
  uv run ruff check . --fix

# Отформатировать код через Ruff formatter.
format:
  uv run ruff format .
