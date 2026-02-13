from uuid import UUID
from pydantic import BaseModel, validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from schemas.branch import IdName

class AdvancePaymentTripRead(BaseModel):
    trip_id: UUID
    type: str
    customer_name: str
    customer_code: str
    # vendor_id: UUID
    vendor_name: str
    vendor_code: str
    trip_code: str
    trip_date: date
    trip_rate: Decimal
    advance: Decimal
    remaining: Decimal  # Remaining amount to be paid
    
    class Config:
        from_attributes = True

class AdvancePaymentTripList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: list[AdvancePaymentTripRead] = []


class AdvancePaymentBase(BaseModel):
    # customer_id: UUID
    # vendor_id: UUID
    trip_id: UUID
    payment_date: date | None = None
    utr_no: Optional[str] = None
    amount: Decimal
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v
    
    # @validator('utr_no')
    # def validate_utr_no(cls, v):
    #     if not v or v.strip() == "":
    #         raise ValueError('UTR number is required')
    #     return v.strip().upper()


class AdvancePaymentCreate(AdvancePaymentBase):
    payment_for_customer: bool = False


class AdvancePaymentUpdate(BaseModel):
    # customer_id: Optional[UUID] = None
    # vendor_id: Optional[UUID] = None
    trip_id: Optional[UUID] = None
    payment_date: date | None = None
    utr_no: Optional[str] = None
    amount: Optional[Decimal] = None
    payment_for_customer: bool = False

    
    @validator('amount')
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v


class TripDetails(BaseModel):
    """Simplified trip details for response"""
    id: UUID
    trip_code: str


class AdvancePaymentRead(BaseModel):
    """Read schema without customer_id, vendor_id, trip_id (shown in nested objects)"""
    id: UUID
    payment_date: date | None = None
    utr_no: str | None = None
    amount: Decimal
    payment_type: str | None = None
    action_required: bool
    is_paid_amount: bool
    is_payment_due: bool
    
    # Nested relationships (these contain the IDs)
    # customer: IdName
    # vendor: IdName
    # trip: TripDetails
    
    # Audit fields
    # is_active: bool
    created_at: datetime
    # updated_at: datetime
    # created_by: Optional[UUID] = None
    # updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class AdvancePaymentList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    paid_amount: Optional[Decimal] = None
    balance_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    results: list[AdvancePaymentRead] = []
