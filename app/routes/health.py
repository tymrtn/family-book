from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.person import Person

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        result = await db.execute(select(func.count()).select_from(Person.__table__))
        persons_count = result.scalar() or 0
        db_status = "connected"
    except Exception:
        db_status = "error"
        persons_count = 0

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "version": "0.1.0",
        "persons_count": persons_count,
    }
