from typing import Optional
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Todo, Priority
from app.schemas import (
    TodoCreate, TodoUpdate, TodoResponse, TodoListResponse,
    BulkDeleteRequest, BulkCompleteRequest,
)

router = APIRouter()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _apply_filters(stmt, completed: Optional[bool], priority: Optional[Priority]):
    if completed is not None:
        stmt = stmt.where(Todo.completed == completed)
    if priority is not None:
        stmt = stmt.where(Todo.priority == priority)
    return stmt


# ─── List / filter / paginate ────────────────────────────────────────────────

@router.get("/", response_model=TodoListResponse, summary="List todos")
async def list_todos(
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Full-text search on title"),
    sort_by: str = Query("created_at", enum=["created_at", "updated_at", "due_date", "priority", "title"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base = select(Todo)
    base = _apply_filters(base, completed, priority)
    if search:
        base = base.where(Todo.title.ilike(f"%{search}%"))

    # count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # sort
    col = getattr(Todo, sort_by)
    base = base.order_by(col.desc() if order == "desc" else col.asc())

    # paginate
    offset = (page - 1) * page_size
    base = base.offset(offset).limit(page_size)
    rows = (await db.execute(base)).scalars().all()

    return TodoListResponse(
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


# ─── Create ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED, summary="Create a todo")
async def create_todo(payload: TodoCreate, db: AsyncSession = Depends(get_db)):
    todo = Todo(**payload.model_dump())
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


# ─── Get by id ───────────────────────────────────────────────────────────────

@router.get("/{todo_id}", response_model=TodoResponse, summary="Get a single todo")
async def get_todo(todo_id: int, db: AsyncSession = Depends(get_db)):
    todo = await db.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


# ─── Update ──────────────────────────────────────────────────────────────────

@router.put("/{todo_id}", response_model=TodoResponse, summary="Update a todo")
async def update_todo(todo_id: int, payload: TodoUpdate, db: AsyncSession = Depends(get_db)):
    todo = await db.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(todo, key, val)
    await db.flush()
    await db.refresh(todo)
    return todo


# ─── Toggle completed ────────────────────────────────────────────────────────

@router.patch("/{todo_id}/toggle", response_model=TodoResponse, summary="Toggle completion")
async def toggle_todo(todo_id: int, db: AsyncSession = Depends(get_db)):
    todo = await db.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.completed = not todo.completed
    await db.flush()
    await db.refresh(todo)
    return todo


# ─── Delete ──────────────────────────────────────────────────────────────────

@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a todo")
async def delete_todo(todo_id: int, db: AsyncSession = Depends(get_db)):
    todo = await db.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    await db.delete(todo)


# ─── Bulk delete ─────────────────────────────────────────────────────────────

@router.delete("/bulk/delete", status_code=status.HTTP_204_NO_CONTENT, summary="Bulk delete todos")
async def bulk_delete(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Todo).where(Todo.id.in_(payload.ids)))


# ─── Bulk complete ────────────────────────────────────────────────────────────

@router.patch("/bulk/complete", response_model=list[TodoResponse], summary="Bulk mark todos complete/incomplete")
async def bulk_complete(payload: BulkCompleteRequest, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Todo).where(Todo.id.in_(payload.ids)).values(completed=payload.completed)
    )
    result = await db.execute(select(Todo).where(Todo.id.in_(payload.ids)))
    return result.scalars().all()
