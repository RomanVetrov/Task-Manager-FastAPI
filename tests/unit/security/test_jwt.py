from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.security import jwt as jwt_service
from app.security.jwt import (
    TokenExpired,
    TokenInvalid,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def _unix_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def test_create_and_decode_access_token_roundtrip() -> None:
    """Проверяет, что access-токен корректно создаётся и декодируется обратно."""
    token = create_access_token(subject="user-123")

    decoded = decode_access_token(token)

    assert decoded.sub == "user-123"
    assert decoded.payload["type"] == "access"


def test_decode_access_token_rejects_refresh_token() -> None:
    """Проверяет, что refresh-токен нельзя декодировать как access-токен."""
    refresh_token, _ = create_refresh_token(subject="user-123")

    with pytest.raises(TokenInvalid, match="Ожидался access токен"):
        decode_access_token(refresh_token)


def test_decode_refresh_token_requires_jti() -> None:
    """Проверяет, что refresh-токен без jti отвергается как невалидный."""
    payload = {
        "sub": "user-123",
        "iat": _unix_now(),
        "exp": _unix_now() + 60,
        "type": "refresh",
    }
    token_without_jti = jwt.encode(
        payload=payload,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(TokenInvalid, match="отсутствует jti"):
        decode_refresh_token(token_without_jti)


def test_decode_access_token_raises_for_expired_token() -> None:
    """Проверяет, что истёкший access-токен приводит к TokenExpired."""
    expired_token = create_access_token(
        subject="user-123",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenExpired, match="истёк"):
        decode_access_token(expired_token)


def test_create_access_token_merges_extra_claims() -> None:
    """Проверяет, что custom claims попадают в payload access-токена."""
    token = create_access_token(
        subject="user-123",
        extra_claims={"role": "admin"},
    )

    decoded = decode_access_token(token)

    assert decoded.payload["role"] == "admin"


def test_decode_access_token_rejects_non_string_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что _decode_token отклоняет payload с нестроковым sub."""
    monkeypatch.setattr(
        jwt_service.jwt,
        "decode",
        lambda **_: {
            "sub": 123,
            "iat": _unix_now(),
            "exp": _unix_now() + 60,
            "type": "access",
        },
    )

    with pytest.raises(TokenInvalid, match="Ошибка субъекта"):
        decode_access_token("token")


def test_decode_access_token_rejects_unknown_token_type() -> None:
    """Проверяет, что токен с произвольным type отклоняется как невалидный."""
    payload = {
        "sub": "user-123",
        "iat": _unix_now(),
        "exp": _unix_now() + 60,
        "type": "unknown",
    }
    token = jwt.encode(
        payload=payload,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(TokenInvalid, match="Некорректный тип токена"):
        decode_access_token(token)


def test_decode_refresh_token_rejects_access_token_type() -> None:
    """Проверяет, что access-токен нельзя декодировать как refresh-токен."""
    access_token = create_access_token(subject="user-123")

    with pytest.raises(TokenInvalid, match="Ожидался refresh токен"):
        decode_refresh_token(access_token)
