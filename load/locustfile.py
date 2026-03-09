from __future__ import annotations

import os
import random
from datetime import date, timedelta
from uuid import uuid4

from gevent.lock import Semaphore
from locust import HttpUser, between, task

API_PREFIX = "/api/v1"
REGISTER_PATH = f"{API_PREFIX}/auth/register"
LOGIN_PATH = f"{API_PREFIX}/auth/login"
TASKS_PATH = f"{API_PREFIX}/tasks"

LOADTEST_EMAIL = os.getenv("LOCUST_EMAIL", "loadtest@example.com")
LOADTEST_PASSWORD = os.getenv("LOCUST_PASSWORD", "StrongPass123!")
ENABLE_AUTH_ABUSE = os.getenv("LOCUST_ENABLE_AUTH_ABUSE", "true").lower() in {
    "1",
    "true",
    "yes",
}


class SharedAuthState:
    """Общее состояние токена для всех виртуальных пользователей процесса Locust."""

    lock = Semaphore()
    access_token: str | None = None


class ApiUser(HttpUser):
    """Основной пользовательский поток: задачи под авторизованным токеном."""

    wait_time = between(0.3, 1.2)
    weight = 5

    access_token: str | None
    my_task_ids: list[str]

    def on_start(self) -> None:
        self.my_task_ids = []
        self.access_token = self._get_shared_access_token()

    def _auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            self.access_token = self._get_shared_access_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    def _register_loadtest_user(self) -> None:
        payload = {
            "email": LOADTEST_EMAIL,
            "password": LOADTEST_PASSWORD,
        }
        # 201 - зарегистрировали, 409 - уже есть. Оба состояния для теста валидны.
        self.client.post(
            REGISTER_PATH,
            json=payload,
            name="POST /api/v1/auth/register (bootstrap)",
        )

    def _login_loadtest_user(self) -> str | None:
        response = self.client.post(
            LOGIN_PATH,
            data={"username": LOADTEST_EMAIL, "password": LOADTEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /api/v1/auth/login (bootstrap)",
        )
        if response.status_code != 200:
            return None
        body = response.json()
        token = body.get("access_token")
        return token if isinstance(token, str) and token else None

    def _get_shared_access_token(self) -> str | None:
        if SharedAuthState.access_token:
            return SharedAuthState.access_token

        with SharedAuthState.lock:
            if SharedAuthState.access_token:
                return SharedAuthState.access_token

            self._register_loadtest_user()
            SharedAuthState.access_token = self._login_loadtest_user()
            return SharedAuthState.access_token

    def _pick_task_id(self) -> str | None:
        if self.my_task_ids:
            return random.choice(self.my_task_ids)

        response = self.client.get(
            TASKS_PATH,
            headers=self._auth_headers(),
            name="GET /api/v1/tasks",
        )
        if response.status_code != 200:
            return None

        tasks = response.json()
        if not isinstance(tasks, list) or not tasks:
            return None

        ids = [item.get("id") for item in tasks if isinstance(item, dict)]
        ids = [task_id for task_id in ids if isinstance(task_id, str)]
        if ids:
            self.my_task_ids.extend(ids)
            return random.choice(ids)
        return None

    @task(6)
    def list_tasks(self) -> None:
        self.client.get(
            TASKS_PATH,
            headers=self._auth_headers(),
            name="GET /api/v1/tasks",
        )

    @task(3)
    def create_task(self) -> None:
        payload = {
            "title": f"load-task-{uuid4().hex[:8]}",
            "description": "Created by locust",
            "status": "todo",
            "priority": "medium",
            "due_date": str(date.today() + timedelta(days=2)),
        }

        with self.client.post(
            TASKS_PATH,
            json=payload,
            headers=self._auth_headers(),
            name="POST /api/v1/tasks",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                task_id = response.json().get("id")
                if isinstance(task_id, str):
                    self.my_task_ids.append(task_id)
                response.success()
            elif response.status_code == 401:
                # Токен истёк: логинимся один раз глобально и продолжаем нагрузку.
                SharedAuthState.access_token = None
                self.access_token = self._get_shared_access_token()
                response.failure("401 on create_task: token refresh needed")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def update_task(self) -> None:
        task_id = self._pick_task_id()
        if not task_id:
            return

        payload = {
            "status": random.choice(["todo", "in_progress", "done"]),
            "priority": random.choice(["low", "medium", "high"]),
        }
        self.client.patch(
            f"{TASKS_PATH}/{task_id}",
            json=payload,
            headers=self._auth_headers(),
            name="PATCH /api/v1/tasks/{task_id}",
        )

    @task(1)
    def delete_task(self) -> None:
        if not self.my_task_ids:
            return

        task_id = random.choice(self.my_task_ids)
        with self.client.delete(
            f"{TASKS_PATH}/{task_id}",
            headers=self._auth_headers(),
            name="DELETE /api/v1/tasks/{task_id}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.my_task_ids = [
                    item for item in self.my_task_ids if item != task_id
                ]
                response.success()
            elif response.status_code in {403, 404}:
                # Параллельные пользователи могли уже удалить/изменить задачу.
                self.my_task_ids = [
                    item for item in self.my_task_ids if item != task_id
                ]
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class AuthAbuseUser(HttpUser):
    """Негативный поток для проверки защиты auth (401/429)."""

    wait_time = between(0.5, 1.5)
    weight = 1 if ENABLE_AUTH_ABUSE else 0

    @task
    def invalid_login(self) -> None:
        with self.client.post(
            LOGIN_PATH,
            data={"username": LOADTEST_EMAIL, "password": "wrong-password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /api/v1/auth/login (invalid)",
            catch_response=True,
        ) as response:
            if response.status_code in {401, 429}:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
