from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel


class IdName(SQLModel):
    id: UUID
    name: str


CountryIdName = IdName
StateIdName = IdName
DistrictIdName = IdName
CityIdName = IdName


class AddressCreate(BaseModel):
    pin_code: str
    location: str
    country_id: UUID
    state_id: UUID
    district_id: UUID
    city_id: UUID


class AddressRead(BaseModel):
    pin_code: str
    location: str
    country: CountryIdName
    state: StateIdName
    district: DistrictIdName
    city: CityIdName


# ✅ New: Manager Details Schema
class ManagerDetails(BaseModel):
    """Detailed manager information"""
    employee_id: UUID
    employee_code: str
    name: str
    mobile: str
    email: str
    address: dict
    employee_pic: str | None = None 
    
    class Config:
        from_attributes = True


class BranchBase(BaseModel):
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None


class BranchCreate(BranchBase):
    address: AddressCreate


class BranchUpdate(BaseModel):
    name: str | None = None
    address: AddressCreate | None = None


class BranchRead(BranchBase):
    id: UUID
    code: str
    is_active: bool
    address: AddressRead
    branch_manager: Optional[ManagerDetails] = None  # ✅ Add branch manager
    national_manager: Optional[ManagerDetails] = None  # ✅ Add national manager
    email: Optional[str] = None
    mobile: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class BranchListRead(SQLModel):
    id: UUID
    name: str
    code: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    address: dict 
    branch_region: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class BranchList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[BranchListRead] = []  


class BranchManagerUpdate(BaseModel):
    """Schema for updating branch manager"""
    manager_employee_id: UUID
