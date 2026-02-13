from typing import Optional,List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from .district import DistrictRead

class CityBase(BaseModel):
    name: str

class CityCreate(CityBase):
    district_id: UUID

class CityUpdate(BaseModel):
    name: str | None = None
    district_id: UUID | None = None


class CityRead(CityBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None

    updated_by: UUID | None = None

    district: DistrictRead  # Optionally expose district name or full object

    class Config:
        from_attributes = True

class CityList(BaseModel):
    total: int
    next:  str | None = None
    previous:  str | None = None
    results: List[CityRead] = []
