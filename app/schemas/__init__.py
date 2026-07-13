from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from app.models import Priority


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, examples=["Buy groceries"])
    description: Optional[str] = Field(None, max_length=2000)
    priority: Priority = Priority.medium
    due_date: Optional[datetime] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    completed: Optional[bool] = None
    priority: Optional[Priority] = None
    due_date: Optional[datetime] = None


class TodoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: Priority
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TodoListResponse(BaseModel):
    items: List[TodoResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BulkDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1)


class BulkCompleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1)
    completed: bool = True
