from datetime import datetime, timezone
import enum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"), default=Priority.medium, nullable=False, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Todo id={self.id} title={self.title!r} completed={self.completed}>"
