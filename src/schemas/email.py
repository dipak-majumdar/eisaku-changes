from pydantic import BaseModel, Field as PydanticField
from uuid import UUID
from typing import List, Optional
from datetime import date, datetime, timedelta



class EmailBase(BaseModel):
    id: UUID
    subject: str
    body: str
    recipient_email: str
    status: Optional[str] = None
    
    # Audit fields
    is_active: Optional[bool] = None
    created_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class EmailList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[EmailBase] = [] 

class EmailRead(EmailBase):
    pass


class EmailBulkDelete(BaseModel):
    email_ids: List[UUID] = PydanticField(..., description="List of email IDs to delete")
