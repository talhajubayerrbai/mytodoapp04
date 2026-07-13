import os
from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter()


@router.get("/info", summary="API information")
async def api_info():
    db_status = "unknown"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "app": "fastapi",
        "version": "1.0.0",
        "db": db_status,
        "env": os.getenv("APP_ENV", "production"),
    }
