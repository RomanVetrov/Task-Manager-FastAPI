from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import UserInactive, UserNotFound, validate_refresh_subject


async def require_active_refresh_user(session: AsyncSession, user_id: UUID) -> None:
    """Проверяет, что пользователь для refresh существует и активен."""
    try:
        await validate_refresh_subject(session, user_id)
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия недействительна (пользователь не найден)",
        )
    except UserInactive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )
