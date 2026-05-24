from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.tag_repo import TagRepository
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.models.tag import Tag

router = APIRouter()


@router.get("/", response_model=List[TagRead])
async def list_tags(db: AsyncSession = Depends(get_db)):
    repo = TagRepository(db)
    items, _ = await repo.list_all(limit=500, offset=0)
    return items


@router.post("/", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(data: TagCreate, db: AsyncSession = Depends(get_db)):
    repo = TagRepository(db)
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=409, detail="Tag with this name already exists")
    tag = Tag(**data.model_dump())
    return await repo.create(tag)


@router.get("/{tag_id}", response_model=TagRead)
async def get_tag(tag_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TagRepository(db)
    tag = await repo.get_by_id(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.put("/{tag_id}", response_model=TagRead)
async def update_tag(tag_id: UUID, data: TagUpdate, db: AsyncSession = Depends(get_db)):
    repo = TagRepository(db)
    tag = await repo.get_by_id(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tag, field, value)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = TagRepository(db)
    tag = await repo.get_by_id(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    await repo.hard_delete(tag)
    return None
