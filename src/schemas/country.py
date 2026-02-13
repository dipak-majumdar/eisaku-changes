from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class CountryBase(BaseModel):
    name: str

class CountryCreate(CountryBase):
    pass

class CountryUpdate(BaseModel):
    name: str | None = None



class CountryRead(CountryBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True 



class CountryList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[CountryRead] = []
