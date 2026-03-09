from __future__ import annotations

import pytest

from app.config import settings
from app.security.password import hash_password, verify_password


@pytest.mark.asyncio
async def test_hash_and_verify_password_roundtrip() -> None:
    hashed = await hash_password(password="StrongPass123!")

    assert await verify_password(password="StrongPass123!", hashed_password=hashed)


@pytest.mark.asyncio
async def test_verify_password_returns_false_for_invalid_password() -> None:
    hashed = await hash_password(password="StrongPass123!")

    assert not await verify_password(password="wrong-pass", hashed_password=hashed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password",
    ["x" * (settings.ARGON_MAX_PASSWORD_LEN + 1)],
)
async def test_hash_password_rejects_overlong_password(password: str) -> None:
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
    hashed = await hash_password(password="StrongPass123!")

    assert not await verify_password(password=password, hashed_password=hashed)
