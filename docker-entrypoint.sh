#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  set -- uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-4}"
fi

alembic upgrade head
exec "$@"
