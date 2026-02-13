from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import TYPE_CHECKING, Optional

from sqlmodel import SQLModel
from schemas.branch import IdName, CountryIdName, StateIdName, DistrictIdName, CityIdName

from schemas.user import UserBasic

if TYPE_CHECKING:
    from .user import UserRead

class AddressCreate(BaseModel):
    pin_code: str
    location: str
    country_id: UUID
    state_id: UUID
    district_id: UUID
    city_id: UUID
    region_id: UUID | None = None

class AddressRead(BaseModel):
    pin_code: str
    location: str
    country: CountryIdName
    state: StateIdName
    district: DistrictIdName
    city: CityIdName
    region: IdName | None = None



class EmployeeBase(BaseModel):
    employee_code: str
    employee_pic: str

class EmployeeCreate(EmployeeBase):
    user_id: UUID
    branch_id: UUID | None = None
    manager_id: UUID | None = None
    address: AddressCreate

class EmployeeUpdate(BaseModel):
    user_id: UUID | None = None
    branch_id: UUID | None = None
    manager_id: UUID | None = None
    address: AddressCreate | None = None
    employee_code: str | None = None
    employee_pic: str | None = None

class EmployeeRead(EmployeeBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None
    user: UserBasic | None = None
    branch: IdName | None = None
    manager: IdName | None = None
    reports: list[IdName] = []
    address: AddressRead

    class Config:
        from_attributes = True


class EmployeeListRead(SQLModel):
    id: UUID
    employee_code: str
    employee_pic: str
    user: Optional[IdName] = None  
    role: Optional[IdName] = None
    branch: Optional[IdName] = None
    manager: Optional[IdName] = None
    address: dict
    is_active: bool
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class EmployeeList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[EmployeeListRead] = []



class EmployeeDetails(BaseModel):
    id: UUID
    employee_code: str
    employee_pic: str
    branch: IdName | None = None
    manager: IdName | None = None
    address: AddressRead

    class Config:
        from_attributes = True