from typing import TYPE_CHECKING, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Field, Relationship
from db.base import BaseTable
import enum

if TYPE_CHECKING:
    from .customer import Customer
    from .vendor import Vendor
    from .user import User
    from .complaint_history import ComplaintStatusHistory

class UserTypeEnum(str, enum.Enum):
    CUSTOMER = "Customer"
    VENDOR = "Vendor"


class ComplaintStatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    INPROGRESS = "IN PROGRESS"
    CLOSED = "CLOSED"


class SubjectTypeEnum(str, enum.Enum):
    BLOCK = "Block"
    OTHER = "Other"


class Complaint(BaseTable, table=True):
    __tablename__ = "marketline_complaints"

    # User identification
    user_type: UserTypeEnum = Field(nullable=False)
    vendor_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vendors.id")
    customer_id: Optional[UUID] = Field(default=None, foreign_key="marketline_customers.id")
    
    # Complaint details
    status: ComplaintStatusEnum = Field(default=ComplaintStatusEnum.OPEN)
    subject_type: SubjectTypeEnum = Field(nullable=False)
    custom_subject: Optional[str] = Field(default=None, max_length=255)
    complaint_date: date = Field(nullable=False)
    description: str = Field(nullable=False, max_length=1000)
    code: Optional[str] = Field(default=None, max_length=15, unique=True, index=True)
    
    status_note: Optional[str] = Field(default=None, max_length=1000)
    # Relationships
    vendor: Optional["Vendor"] = Relationship()
    customer: Optional["Customer"] = Relationship()
    status_history: list["ComplaintStatusHistory"] = Relationship(  # ✅ Must match back_populates
        back_populates="complaint",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "ComplaintStatusHistory.changed_at"
        }
    )