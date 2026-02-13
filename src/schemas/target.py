# schemas/target.py

from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal
from sqlmodel import SQLModel

from models.target import TargetStatusEnum


class IdName(BaseModel):
    id: UUID
    name: str


class TargetBase(BaseModel):
    start_date: date
    end_date: date
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('end_date must be after start_date')
        return v


class TargetCreate(BaseModel):
    branch_id: UUID
    no_of_trip: int = Field(gt=0, description="Number of trips target")
    total_margin: Decimal = Field(ge=0, description="Total margin target")
    total_revenue: Decimal = Field(ge=0, description="Total revenue target")
    start_date: date
    end_date: date
    @validator('start_date')
    def validate_start_date_not_past(cls, v):
        """Ensure start date is not in the past"""
        today = date.today()
        if v < today:
            raise ValueError('start_date cannot be in the past')
        return v
    @validator('end_date')
    def validate_end_date(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('end_date must be after start_date')
        return v


class TargetUpdate(BaseModel):
    """Full update schema - all fields required for PUT"""
    branch_id: UUID
    no_of_trip: int = Field(gt=0)
    total_margin: Decimal = Field(ge=0)
    total_revenue: Decimal = Field(ge=0)
    start_date: date
    end_date: date
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        start_date = values.get('start_date')
        if start_date and v <= start_date:
            raise ValueError('end_date must be after start_date')
        return v


# ✅ Single unified read schema
class TargetRead(SQLModel):
    id: UUID
    start_date: date
    end_date: date
    status: TargetStatusEnum
    rejection_reason: Optional[str] = None
    
    
    trip: dict
    margin: dict
    revenue: dict
    branch: dict = Field(alias="branch_info")  
    
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True  



class TargetDetail(SQLModel):
    id: UUID
    start_date: date
    end_date: date
    status: TargetStatusEnum
    rejection_reason: Optional[str] = None
    
    # Grouped data from properties
    trip: dict
    margin: dict
    revenue: dict
    branch: dict = Field(alias="branch_detail")  
    
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True


class TargetList(BaseModel):
    total: int
 
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[TargetRead] = []





class TargetStatusUpdate(BaseModel):
    status: TargetStatusEnum
    rejection_reason: Optional[str] = None
    
    @validator('rejection_reason')
    def validate_rejection_reason(cls, v, values):
        status = values.get('status')
        if status == TargetStatusEnum.REJECTED:
            if not v or v.strip() == "":
                raise ValueError("rejection_reason is required when status is Rejected")
        return v

class BranchPerformanceMetric(BaseModel):
    """Metric with target and achieved values"""
    target: Decimal
    achieved: Decimal
  

class BranchPerformance(BaseModel):
    """Branch performance data"""
    branch_id: UUID
    branch_code: str
    branch_name: str
    
    trips: BranchPerformanceMetric
    revenue: BranchPerformanceMetric
    margin: BranchPerformanceMetric
    
    target_status: Optional[str] = None
    target_period: Optional[str] = None  # e.g., "2025-11-01 to 2025-11-30"

class BranchPerformanceList(BaseModel):
    """List of branch performances"""
    total: int
    results: list[BranchPerformance]