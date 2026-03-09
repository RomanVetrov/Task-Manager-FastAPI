"""Утилиты для работы с JWT токенами."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from opentelemetry import trace
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import settings

tracer = trace.get_tracer(__name__)


def create_access_token(
    *,
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Создаёт подписанный access-токен с TTL из настроек (или expires_delta)."""
    with tracer.start_as_current_span("security.jwt.create_access_token"):
        now = datetime.now(timezone.utc)
        expire = now + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        payload: dict[str, Any] = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "access",
        }
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(
            payload=payload,
            key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )


def create_refresh_token(
    *,
    subject: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """Создаёт refresh-токен с уникальным jti. Возвращает (token, jti)."""
    with tracer.start_as_current_span("security.jwt.create_refresh_token"):
        now = datetime.now(timezone.utc)
        expire = now + (
            expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        jti = uuid4().hex

        payload: dict[str, Any] = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
            "jti": jti,
        }

        token = jwt.encode(
            payload=payload,
            key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return token, jti


class TokenExpired(Exception):
    """Исключение для истёкших токенов."""

    pass


class TokenInvalid(Exception):
    """Исключение для невалидных токенов."""

    pass


@dataclass(frozen=True)
class TokenData:
    """Данные из декодированного JWT токена."""

    sub: str
    payload: dict[str, Any]


def _decode_token(token: str) -> dict[str, Any]:
    """Общая декодировка и базовая валидация JWT."""
    with tracer.start_as_current_span("security.jwt.decode_token"):
        try:
            payload = jwt.decode(
                jwt=token,
                key=settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"require": ["sub", "exp", "type"]},
            )
        except ExpiredSignatureError as e:
            raise TokenExpired("Токен истёк") from e
        except InvalidTokenError as e:
            raise TokenInvalid("Неверный токен/Ошибка валидации токена") from e

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise TokenInvalid("Ошибка субъекта в токене")

        token_type = payload.get("type")
        if token_type not in {"access", "refresh"}:
            raise TokenInvalid("Некорректный тип токена")

        return payload


def decode_access_token(token: str) -> TokenData:
    """Декодирует и валидирует access-токен. Поднимает TokenExpired / TokenInvalid."""
    payload = _decode_token(token)
    if payload.get("type") != "access":
        raise TokenInvalid("Ожидался access токен")
    return TokenData(sub=payload["sub"], payload=payload)


def decode_refresh_token(token: str) -> TokenData:
    """Декодирует и валидирует refresh-токен, проверяет наличие jti."""
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise TokenInvalid("Ожидался refresh токен")

    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti:
        raise TokenInvalid("В refresh токене отсутствует jti")

    return TokenData(sub=payload["sub"], payload=payload)
