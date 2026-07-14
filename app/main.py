from contextlib import asynccontextmanager
import pathlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import health, api
from app.routers.todos import router as todos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (idempotent — Alembic handles migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="mytodoapp04-qa",
    version="1.0.0",
    description="Production-grade Todo API backed by RDS PostgreSQL",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
_static = pathlib.Path(__file__).parent.parent / "public"
if _static.exists():
    app.mount("/public", StaticFiles(directory=str(_static)), name="static")

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(todos_router, prefix="/api/todos", tags=["todos"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    html = pathlib.Path(__file__).parent.parent / "public" / "index.html"
    if html.exists():
        return HTMLResponse(content=html.read_text())
    return HTMLResponse(content="<h1>mytodoapp04-qa is running</h1>")
