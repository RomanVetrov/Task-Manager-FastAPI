from __future__ import annotations

import pytest

from app.config import settings
from app.security.password import get_dummy_hash, hash_password, verify_password


@pytest.mark.asyncio
async def test_hash_and_verify_password_roundtrip() -> None:
    """Проверяет, что хэш от корректного пароля успешно проходит verify."""
    hashed = await hash_password(password="StrongPass123!")

    assert await verify_password(password="StrongPass123!", hashed_password=hashed)


def test_get_dummy_hash_returns_argon2_hash() -> None:
    """Проверяет, что get_dummy_hash возвращает непустой Argon2-хэш."""
    dummy_hash = get_dummy_hash()

    assert dummy_hash
    assert dummy_hash.startswith("$argon2")


@pytest.mark.asyncio
async def test_verify_password_returns_false_for_invalid_password() -> None:
    """Проверяет, что неверный пароль не проходит verify."""
    hashed = await hash_password(password="StrongPass123!")

    assert not await verify_password(password="wrong-pass", hashed_password=hashed)


@pytest.mark.asyncio
async def test_verify_password_returns_false_for_invalid_hash_format() -> None:
    """Проверяет, что verify возвращает False для некорректного формата хэша."""
    assert not await verify_password(
        password="StrongPass123!", hashed_password="not-a-valid-hash"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    ["x" * (settings.ARGON_MAX_PASSWORD_LEN + 1)],
)
async def test_hash_password_rejects_overlong_password(password: str) -> None:
    """Проверяет защиту от слишком длинного пароля на этапе hash."""
    with pytest.raises(ValueError, match="слишком длинный"):
        await hash_password(password=password)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    ["x" * (settings.ARGON_MAX_PASSWORD_LEN + 1)],
)
async def test_verify_password_returns_false_for_overlong_password(
    password: str,
) -> None:
    """Проверяет, что overlong пароль не валидируется и возвращает False."""
    hashed = await hash_password(password="StrongPass123!")

    assert not await verify_password(password=password, hashed_password=hashed)
