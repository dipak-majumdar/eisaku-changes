from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field


class BaseTable(SQLModel):
    """Abstract base model with common fields."""

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    created_by: UUID | None = Field(default=None, nullable=True)
    updated_by: UUID | None = Field(default=None, nullable=True)
