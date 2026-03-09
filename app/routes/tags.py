from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_or_404 import CurrentUser, TagDep
from app.schemas.tag import TagCreate, TagDeleted, TagRead, TagUpdate
from app.services import tag as tag_service
from app.services.tag import TagAlreadyExists

router = APIRouter(prefix="/tags", tags=["tags"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

_TAG_EXISTS_ERROR = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Тег с таким именем уже существует",
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать тег",
)
async def create_tag(
    payload: TagCreate,
    _: CurrentUser,
    session: DbSession,
) -> TagRead:
    try:
        created = await tag_service.create_tag(session, payload)
    except TagAlreadyExists:
        raise _TAG_EXISTS_ERROR
    return TagRead.model_validate(created)


@router.get(
    "",
    summary="Список тегов",
)
async def list_tags(
    _: CurrentUser,
    session: DbSession,
) -> list[TagRead]:
    tags = await tag_service.list_tags(session)
    return [TagRead.model_validate(tag) for tag in tags]


@router.get(
    "/{tag_id}",
    summary="Получить тег по id",
)
async def get_tag(
    _: CurrentUser,
    tag: TagDep,
) -> TagRead:
    return TagRead.model_validate(tag)


@router.patch(
    "/{tag_id}",
    summary="Обновить тег",
)
async def update_tag(
    payload: TagUpdate,
    _: CurrentUser,
    tag: TagDep,
    session: DbSession,
) -> TagRead:
    try:
        updated = await tag_service.update_tag(session, tag, payload)
    except TagAlreadyExists:
        raise _TAG_EXISTS_ERROR
    return TagRead.model_validate(updated)


@router.delete(
    "/{tag_id}",
    summary="Удалить тег",
)
async def delete_tag(
    _: CurrentUser,
    tag: TagDep,
    session: DbSession,
) -> TagDeleted:
    tag_id = await tag_service.delete_tag(session, tag)
    return TagDeleted(id=tag_id)
