"""Pydantic схемы для авторизации и пользователей."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterCreate(BaseModel):
    """Схема для регистрации нового пользователя."""

    email: EmailStr
    password: str = Field(min_length=8, description="Минимум 8 символов")


class RefreshTokenRequest(BaseModel):
    """Схема запроса для refresh/logout операций."""

    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class UserRead(BaseModel):
    """Схема для чтения данных пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    is_active: bool
    created_at: datetime
