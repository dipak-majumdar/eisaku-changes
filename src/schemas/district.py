from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from .state import StateRead




class DistrictBase(BaseModel):
    name: str

class DistrictCreate(DistrictBase):
    state_id: UUID

class DistrictUpdate(BaseModel):
    name: str | None = None
    state_id: UUID | None = None



class DistrictRead(DistrictBase):
    id: UUID
    is_active: bool
    state: StateRead # Optionally expose state name or full object
   

    class Config:
        from_attributes = True

class DistrictList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[DistrictRead] = []