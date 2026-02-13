from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class CustomerDetails(BaseModel):
    """Customer details with id, name, and code"""
    id: UUID
    name: str
    code: str


class VendorDetails(BaseModel):
    """Vendor details with id, name, and code"""
    id: UUID
    name: str
    code: str


class PaymentApprovalHistoryBase(BaseModel):
    trip_id: UUID
    approval_type: str  # 'advance_payment' or 'balance_payment'
    remarks: str | None = None


class PaymentApprovalHistoryCreate(PaymentApprovalHistoryBase):
    pass


class PaymentApprovalHistoryRead(PaymentApprovalHistoryBase):
    id: UUID
    approved_by: UUID
    approver_name: str | None = None
    trip_code: str | None = None
    trip_rate: Decimal | None = None  # Total trip rate (trip_rate + loading/unloading charges)
    trip_remaining: Decimal | None = None  # Remaining amount for the trip
    customer: CustomerDetails | None = None
    vendor: VendorDetails | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentApprovalHistoryList(BaseModel):
    total: int
    next: str | None
    previous: str | None
    results: list[PaymentApprovalHistoryRead]

    class Config:
        from_attributes = True
