from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class Base(BaseModel):
    name: str


class RegionCreate(Base):
    pass


class RegionUpdate(Base):
    pass


class RegionRead(Base):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None

    class Config:
        from_attributes = True 


class RegionList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[RegionRead] = []
