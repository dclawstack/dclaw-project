from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.repositories.tag_repo import TagRepository
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.models.tag import Tag

router = APIRouter()


async def _tag_in_workspace(
    db: AsyncSession, tag_id: UUID, ctx: AuthContext
) -> Tag:
    tag = await TagRepository(db).get_in_workspace(tag_id, ctx.workspace.id)
    if not tag:
        # Same 404 a non-existent tag would yield — never leak the fact
        # that a tag exists in another tenant.
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.get("", response_model=List[TagRead])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await TagRepository(db).list_for_workspace(ctx.workspace.id)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    repo = TagRepository(db)
    existing = await repo.get_by_name_in_workspace(data.name, ctx.workspace.id)
    if existing:
        raise HTTPException(status_code=409, detail="Tag with this name already exists")
    tag = Tag(workspace_id=ctx.workspace.id, **data.model_dump())
    return await repo.create(tag)


@router.get("/{tag_id}", response_model=TagRead)
async def get_tag(
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    return await _tag_in_workspace(db, tag_id, ctx)


@router.put("/{tag_id}", response_model=TagRead)
async def update_tag(
    tag_id: UUID,
    data: TagUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    tag = await _tag_in_workspace(db, tag_id, ctx)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tag, field, value)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_workspace),
):
    tag = await _tag_in_workspace(db, tag_id, ctx)
    await TagRepository(db).hard_delete(tag)
    return None
