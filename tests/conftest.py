from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Минимальные обязательные переменные для загрузки app.config в тестах.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-bytes-value")
