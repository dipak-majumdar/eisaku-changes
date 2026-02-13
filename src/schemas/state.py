
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from .country import CountryRead




class StateBase(BaseModel):
    name: str

class StateCreate(StateBase):
    country_id: UUID  # Inherits all fields from StateBase

class StateUpdate(BaseModel):
    name: str | None = None
    country_id: UUID | None = None


class StateRead(StateBase):
    id: UUID
    is_active: bool
    country: CountryRead 

    class Config:
        from_attributes = True  

class StateList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[StateRead] = []