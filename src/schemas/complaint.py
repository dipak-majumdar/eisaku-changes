from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional

from models.complaint import UserTypeEnum, ComplaintStatusEnum, SubjectTypeEnum
from schemas.branch import IdName


class ComplaintBase(BaseModel):
    user_type: UserTypeEnum
    vendor_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    subject_type: SubjectTypeEnum
    custom_subject: Optional[str] = None
    complaint_date: date
    description: str
    
    @validator('vendor_id', 'customer_id')
    def validate_user_id(cls, v, values):
        user_type = values.get('user_type')
        if user_type == UserTypeEnum.VENDOR and not values.get('vendor_id') and v is None:
            raise ValueError('vendor_id is required when user_type is Vendor')
        if user_type == UserTypeEnum.CUSTOMER and not values.get('customer_id') and v is None:
            raise ValueError('customer_id is required when user_type is Customer')
        return v
    
    @validator('custom_subject')
    def validate_custom_subject(cls, v, values):
        subject_type = values.get('subject_type')
        if subject_type == SubjectTypeEnum.OTHER and not v:
            raise ValueError('custom_subject is required when subject_type is Other')
        return v


class ComplaintStatistics(BaseModel):
    total: int
    open: int
    inprogress: int
    closed: int


class ComplaintCreate(ComplaintBase):
    pass


class ComplaintUpdate(BaseModel):
    user_type: Optional[UserTypeEnum] = None
    vendor_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    subject_type: Optional[SubjectTypeEnum] = None
    custom_subject: Optional[str] = None
    complaint_date: Optional[date] = None
    description: Optional[str] = None


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatusEnum
    note: Optional[str] = None  # Input field from API
    
    @validator('status')
    def validate_status_change(cls, v):
        if v not in [ComplaintStatusEnum.INPROGRESS, ComplaintStatusEnum.CLOSED]:
            raise ValueError('Status can only be changed to INPROGRESS or CLOSED')
        return v


class AddressSchema(BaseModel):
    """Address details"""
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    pincode: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserWithAddress(BaseModel):
    """User details with address for complaint detail"""
    id: UUID
    name: str
    code: str
    address: Optional[AddressSchema] = None
    
    class Config:
        from_attributes = True


class CreatedByUser(BaseModel):
    """User who created the complaint with employee code"""
    id: UUID
    name: str
    code: Optional[str] = None
    
    class Config:
        from_attributes = True


class StatusTimelineItem(BaseModel):
    """Single status change in timeline"""
    status: ComplaintStatusEnum
    changed_at: datetime
    changed_by: Optional[UUID] = None
    changed_by_name: Optional[str] = None
    remarks: Optional[str] = None
    
    class Config:
        from_attributes = True


class StatusTimeline(BaseModel):
    """Complete status timeline"""
    current_status: ComplaintStatusEnum
    timeline: list[StatusTimelineItem] = []


class UserDetails(BaseModel):
    """User details for response"""
    id: UUID
    name: str
    user_type: UserTypeEnum


class IdNameCode(BaseModel):
    """Object with id, name, and code"""
    id: UUID
    name: str
    code: str
    
    class Config:
        from_attributes = True
        
        
class ComplaintRead(BaseModel):
    id: UUID
    user_type: UserTypeEnum
    status: ComplaintStatusEnum
    subject_type: SubjectTypeEnum
    custom_subject: Optional[str] = None
    complaint_date: date
    description: str
    code: Optional[str] = None
    status_note: Optional[str] = None  # ✅ Add status_note to response
    
    vendor: Optional[IdNameCode] = None
    customer: Optional[IdNameCode] = None
    created_by_user: Optional[CreatedByUser] = None
    
    is_active: bool
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True

class ComplaintListOptimized(BaseModel):
    id: UUID
    user_type: UserTypeEnum
    status: ComplaintStatusEnum
    complaint_date: date
    code: Optional[str] = None
    
    vendor: Optional[IdNameCode] = None
    customer: Optional[IdNameCode] = None
    
    is_active: bool
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class TripUserDetails(BaseModel):
    """User details in trip"""
    name: str
    code: str
    branch: str


class UpcomingTripItem(BaseModel):
    """Single upcoming trip"""
    user_details: TripUserDetails
    trip_date: date
    created_at: datetime
    status: str


class ComplaintDetailRead(ComplaintRead):
    """Complaint details with status timeline"""
    status_timeline: StatusTimeline
    balance: Decimal = Decimal("0")
    upcoming_trips: list[UpcomingTripItem] = []
    vendor: Optional[UserWithAddress] = None
    customer: Optional[UserWithAddress] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: str  
        }


class ComplaintList(BaseModel):
   
    next: Optional[str] = None
    previous: Optional[str] = None
    statistics: Optional[ComplaintStatistics] = None
    results: list[ComplaintRead] = []

class ComplaintListDashboard(BaseModel):
    next: Optional[str] = None
    previous: Optional[str] = None
    statistics: Optional[ComplaintStatistics] = None
    results: list[ComplaintListOptimized] = []