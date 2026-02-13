from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class VehicleTypeBase(BaseModel):
    name: str

class VehicleTypeCreate(VehicleTypeBase):
    pass

class VehicleTypeUpdate(BaseModel):
    name: str | None = None



class VehicleTypeRead(VehicleTypeBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True 



class VehicleTypeList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[VehicleTypeRead] = []
