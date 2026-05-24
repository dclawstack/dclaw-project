from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("/", summary="Liveness probe")
async def health_check():
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe (verifies DB connectivity)")
async def health_ready(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail=f"db: {exc}") from exc
    return {"status": "ready"}
