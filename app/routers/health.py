import time
from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter()
_start = time.time()


@router.get("/", summary="Health check")
async def health_check():
    db_status = "unknown"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "uptime": round(time.time() - _start, 1),
        "database": db_status,
    }
