from typing import Optional
from pydantic import BaseModel
from schemas.branch import IdName
from datetime import datetime
from uuid import UUID


class UserBasic(BaseModel):
    """Simplified user schema without nested relationships (avoids circular imports)"""
    id: UUID
    email: str
    mobile: str
    first_name: str
    last_name: str
    role_id: UUID
    is_active: bool
   
    role: IdName | None = None

    class Config:
        from_attributes = True


class Base(BaseModel):
    email: str
    mobile: str
    first_name: str
    last_name: str
    role_id: UUID
    created_at: datetime
    updated_at: datetime


class UserCreate(Base):
    password: str
    branch_id: UUID = None
    manager_id: UUID = None
    country_id: UUID
    state_id: UUID
    district_id: UUID
    city_id: UUID
    pin_code: str
    location: str
    employee_pic: str = ''


class UserUpdate(Base):
    first_name: str | None = None
    last_name: str | None = None
    role_id: UUID | None = None
    branch_id: UUID = None
    manager_id: UUID = None
    country_id: UUID | None = None
    state_id: UUID | None = None
    district_id: UUID | None = None
    city_id: UUID | None = None
    pin_code: str | None = None
    location: str | None = None
    employee_code: str | None = None
    employee_pic: str | None = None


class UserRead(Base):
    id: UUID
    is_active: bool
    role_id: UUID          
    role: str       
    user_code: str | None = None    
    branch_id: UUID | None = None   
    branch_name: str | None = None  
    manager_id: UUID | None = None  
    manager_name: str | None = None 
    address: dict | None = None
    employee_pic: str | None = None

    class Config:
        from_attributes = True




# class UserList(BaseModel):
#     total: int
#     next: str | None = None
#     previous: str | None = None
#     results: list[UserRead] = []


class UserReadWithRole(UserRead):
    role: str


# Import at the end to resolve forward references
from schemas.employee import EmployeeDetails, AddressRead
UserRead.model_rebuild()  # Rebuild to resolve forward references


class AddressMinimal(BaseModel):
    """Minimal address object"""
    country: str | None = None
    state: str | None = None
    district: str | None = None
    city: str | None = None
    pin_code: str | None = None
    location: str | None = None


class UserMinimal(BaseModel):
    """Minimal user data for fast listing"""
    id: UUID
    email: str
    first_name: str
    last_name: str
    mobile: str
    role: str
    address: AddressMinimal | None = None
    is_active: bool
    employee_pic: str
    created_at: datetime
    updated_at: datetime
    
    
    class Config:
        from_attributes = True


class UserMinimalList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[UserMinimal] = []


class UserCheckResponse(BaseModel):
    exists: bool
    field: Optional[str] = None  # "email" or "mobile" if exists
    message: str
    
    class Config:
        from_attributes = True