"""Сервисный слой для работы с авторизацией и регистрацией пользователей."""

from __future__ import annotations

from uuid import UUID

from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import user_repo
from app.security.password import get_dummy_hash, hash_password, verify_password

tracer = trace.get_tracer(__name__)


class UserAlreadyExists(Exception):
    """Email уже занят другим пользователем."""


class UserNotFound(Exception):
    """Пользователь не найден."""


class UserInactive(Exception):
    """Аккаунт пользователя заблокирован."""


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    """Регистрирует нового пользователя. Поднимает UserAlreadyExists если email занят."""
    with tracer.start_as_current_span("auth.register_user"):
        if await user_repo.get_user_by_email(session, email):
            raise UserAlreadyExists(email)
        pass_hash = await hash_password(password=password)
        return await user_repo.create_user(
            session,
            email=email,
            hashed_password=pass_hash,
        )


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    """Проверяет email + пароль. Возвращает пользователя или None если данные неверны."""
    with tracer.start_as_current_span("auth.authenticate_user"):
        user = await user_repo.get_user_by_email(session, email)
        # Проверяем хэш всегда, чтобы не выдавать существование email по времени ответа.
        hashed = user.hashed_password if user else get_dummy_hash()
        if not await verify_password(password=password, hashed_password=hashed):
            return None
        return user


async def authenticate_active_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    """Проверяет email+пароль и активность аккаунта.

    Возвращает пользователя при успехе, None если данные неверны.
    Поднимает UserInactive, если аккаунт заблокирован.
    """
    user = await authenticate_user(session, email, password)
    if not user:
        return None
    if not user.is_active:
        raise UserInactive
    return user


async def validate_refresh_subject(session: AsyncSession, user_id: UUID) -> User:
    """Проверяет, что пользователь для refresh существует и активен."""
    with tracer.start_as_current_span("auth.validate_refresh_subject"):
        user = await user_repo.get_user_by_id(session, user_id)
        if not user:
            raise UserNotFound
        if not user.is_active:
            raise UserInactive
        return user
