# schemas/customer_contact_person.py

from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional


class CustomerContactPersonBase(BaseModel):
    name: str
    mobile: str
    email: EmailStr  # ✅ Validates email format automatically
    customer_id: UUID


class CustomerContactPersonCreate(CustomerContactPersonBase):
    pass  # ✅ No validators needed - validation is in service


class CustomerContactPersonUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None


class CustomerContactPersonRead(CustomerContactPersonBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class CustomerContactPersonList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[CustomerContactPersonRead] = []
