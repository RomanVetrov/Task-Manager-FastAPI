from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from opentelemetry import trace
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.limits.dependencies import rate_limit_by_ip
from app.models.user import User
from app.redis import get_redis
from app.schemas.auth import RefreshTokenRequest, RegisterCreate, TokenPair, UserRead
from app.security.dependences import get_current_user
from app.security.jwt import (
    TokenExpired,
    TokenInvalid,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.security.refresh_guard import require_active_refresh_user
from app.services.auth import (
    UserAlreadyExists,
    UserInactive,
    authenticate_active_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])
tracer = trace.get_tracer(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _refresh_ttl_seconds() -> int:
    """TTL refresh-токена в секундах из настроек (неделя)"""
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _refresh_key(user_id: UUID, jti: str) -> str:
    """Ключ для хранения refresh-токена в Redis: rt:{user_id}:{jti}."""
    return f"rt:{user_id}:{jti}"


def _parse_refresh_token_or_401(refresh_token: str) -> tuple[UUID, str]:
    """Декодирует refresh-токен и возвращает (user_id, jti). Поднимает 401 при ошибке."""
    with tracer.start_as_current_span("auth.parse_refresh_token"):
        try:
            token_data = decode_refresh_token(refresh_token)
        except (TokenExpired, TokenInvalid):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный или истёкший refresh токен",
            )

        try:
            user_id = UUID(token_data.sub)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный идентификатор пользователя в refresh токене",
            )

        jti = str(token_data.payload["jti"])
        return user_id, jti


async def _issue_token_pair(user_id: UUID, redis: Redis) -> TokenPair:
    """Создаёт новую пару токенов и сохраняет jti refresh-токена в Redis."""
    with tracer.start_as_current_span("auth.issue_token_pair"):
        access_token = create_access_token(subject=str(user_id))
        refresh_token, jti = create_refresh_token(subject=str(user_id))

        await redis.set(
            _refresh_key(user_id, jti),
            str(user_id),
            ex=_refresh_ttl_seconds(),
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пользователя",
    dependencies=[
        Depends(rate_limit_by_ip(limit=5, window_seconds=60, scope="auth_register"))
    ],
)
async def create_user(
    payload: RegisterCreate,
    session: DbSession,
) -> UserRead:
    try:
        new_user = await register_user(session, payload.email, payload.password)
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким Email уже зарегистрирован",
        )
    return UserRead.model_validate(new_user)


@router.post(
    "/login",
    summary="Вход в систему",
    dependencies=[
        Depends(rate_limit_by_ip(limit=10, window_seconds=60, scope="auth_login"))
    ],
)
async def login_user(
    form_data: LoginForm,
    session: DbSession,
    redis: RedisClient,
) -> TokenPair:
    try:
        user = await authenticate_active_user(
            session,
            form_data.username,
            form_data.password,
        )
    except UserInactive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "bearer"},
        )

    return await _issue_token_pair(user.id, redis)


@router.post(
    "/refresh",
    summary="Обновить access/refresh токены",
    dependencies=[
        Depends(rate_limit_by_ip(limit=10, window_seconds=60, scope="auth_refresh"))
    ],
)
async def refresh_token_pair(
    payload: RefreshTokenRequest,
    session: DbSession,
    redis: RedisClient,
) -> TokenPair:
    user_id, jti = _parse_refresh_token_or_401(payload.refresh_token)

    await require_active_refresh_user(session, user_id)

    deleted = await redis.delete(_refresh_key(user_id, jti))
    if deleted != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh токен отозван или уже использован",
        )

    return await _issue_token_pair(user_id, redis)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход из системы",
)
async def logout_user(
    payload: RefreshTokenRequest,
    session: DbSession,
    redis: RedisClient,
) -> Response:
    user_id, jti = _parse_refresh_token_or_401(payload.refresh_token)

    await require_active_refresh_user(session, user_id)

    await redis.delete(_refresh_key(user_id, jti))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", summary="Получить текущего пользователя")
async def current_user(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
