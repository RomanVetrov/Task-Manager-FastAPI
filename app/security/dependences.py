"""FastAPI зависимости для аутентификации и авторизации."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.repositories.user_repo import get_user_by_id
from app.security.jwt import TokenExpired, TokenInvalid, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Декодирует access-токен и возвращает активного пользователя. 401/403 при ошибке."""
    # 1. Проверка токена
    try:
        token_data = decode_access_token(token)
    except (TokenExpired, TokenInvalid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истёкший токен. Войдите заново.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Проверка user_id
    try:
        user_id = uuid.UUID(token_data.sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный идентификатор в токене",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Поиск пользователя
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия недействительна (пользователь не найден)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Проверка активности
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь в поддержку.",
        )

    return user
