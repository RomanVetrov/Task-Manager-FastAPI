from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_or_404 import CurrentUser, TagDep
from app.schemas.tag import TagCreate, TagDeleted, TagRead, TagUpdate
from app.services import tag as tag_service
from app.services.tag import TagAlreadyExists

router = APIRouter(prefix="/tags", tags=["tags"])

_TAG_EXISTS_ERROR = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Тег с таким именем уже существует",
)


@router.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тег",
)
async def create_tag(
    payload: TagCreate,
    _: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> TagRead:
    try:
        created = await tag_service.create_tag(session, payload)
    except TagAlreadyExists:
        raise _TAG_EXISTS_ERROR
    return TagRead.model_validate(created)


@router.get(
    "",
    response_model=list[TagRead],
    summary="Список тегов",
)
async def list_tags(
    _: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> list[TagRead]:
    tags = await tag_service.list_tags(session)
    return [TagRead.model_validate(tag) for tag in tags]


@router.get(
    "/{tag_id}",
    response_model=TagRead,
    summary="Получить тег по id",
)
async def get_tag(
    _: CurrentUser,
    tag: TagDep,
) -> TagRead:
    return TagRead.model_validate(tag)


@router.patch(
    "/{tag_id}",
    response_model=TagRead,
    summary="Обновить тег",
)
async def update_tag(
    payload: TagUpdate,
    _: CurrentUser,
    tag: TagDep,
    session: AsyncSession = Depends(get_db),
) -> TagRead:
    try:
        updated = await tag_service.update_tag(session, tag, payload)
    except TagAlreadyExists:
        raise _TAG_EXISTS_ERROR
    return TagRead.model_validate(updated)


@router.delete(
    "/{tag_id}",
    response_model=TagDeleted,
    summary="Удалить тег",
)
async def delete_tag(
    _: CurrentUser,
    tag: TagDep,
    session: AsyncSession = Depends(get_db),
) -> TagDeleted:
    tag_id = await tag_service.delete_tag(session, tag)
    return TagDeleted(id=tag_id)
