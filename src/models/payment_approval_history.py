from typing import TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship
from db.base import BaseTable

if TYPE_CHECKING:
    from .trip import Trip
    from .user import User


class PaymentApprovalHistory(BaseTable, table=True):
    __tablename__ = "marketline_payment_approval_history"

    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)
    approval_type: str = Field(max_length=50, index=True, nullable=False)  # 'advance_payment' or 'balance_payment'
    approved_by: UUID = Field(foreign_key="marketline_users.id", nullable=False)
    remarks: str | None = Field(default=None, max_length=500)
    
    # Relationships
    trip: "Trip" = Relationship()
    approver: "User" = Relationship()
