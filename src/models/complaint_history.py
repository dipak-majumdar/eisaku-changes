# models/complaint_history.py

from uuid import UUID
from datetime import datetime
from sqlmodel import Field, Relationship
from typing import TYPE_CHECKING, Optional
import enum

from db.base import BaseTable

# ✅ Move enum import inside TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from .complaint import Complaint, ComplaintStatusEnum
    from .user import User
else:
    # ✅ Define enum directly here OR import from a separate enums file
    class ComplaintStatusEnum(str, enum.Enum):
        OPEN = "OPEN"
        INPROGRESS = "IN PROGRESS"
        CLOSED = "CLOSED"

class ComplaintStatusHistory(BaseTable, table=True):
    __tablename__ = "marketline_complaint_status_history"
    
    complaint_id: UUID = Field(foreign_key="marketline_complaints.id", nullable=False)
    status: str = Field(nullable=False)  # ✅ Use str instead of enum for the column
    changed_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    changed_by: Optional[UUID] = Field(default=None, foreign_key="marketline_users.id")
    remarks: Optional[str] = Field(default=None, max_length=500)
    
    # Relationships
    complaint: "Complaint" = Relationship(back_populates="status_history")
    changed_by_user: Optional["User"] = Relationship()
