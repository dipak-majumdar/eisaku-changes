from pydantic import BaseModel, Field as PydanticField, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List

class NotificationBase(BaseModel):
    notification_type: str
    message: str

class NotificationCreate(NotificationBase):
    user_ids: Optional[List[str]] = None  # Optional for broadcast notifications
    role: Optional[str] = None
    # Action buttons support
    action_required: bool = False
    action_data: Optional[Dict[str, Any]] = None
    action_deadline: Optional[datetime] = None

class NotificationRead(NotificationBase):
    id: UUID
    user_ids: Optional[List[str]] = None
    role: Optional[str] = None
    
    # Action buttons support
    action_required: bool = False
    action_data: Optional[str] = None  # JSON string from database
    action_deadline: Optional[datetime] = None
    
    # Status fields
    is_read: bool
    read_at: Optional[datetime] = None
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    
    @field_validator('user_ids', mode='before')
    @classmethod
    def parse_user_ids(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    class Config:
        from_attributes = True

class NotificationList(BaseModel):
    total: int
    unread_count: int
    results: List[NotificationRead]

# New schemas for enhanced features
class NotificationAction(BaseModel):
    action: str = PydanticField(..., description="Action to take: accept, reject, delete, etc.")
    action_data: Optional[Dict[str, Any]] = None

class NotificationActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class NotificationBulkAction(BaseModel):
    notification_ids: List[str] = PydanticField(..., description="List of notification IDs")
    action: str = PydanticField(..., description="Action to take: mark_read, delete, etc.")

class NotificationCount(BaseModel):
    total: int
    unread: int
    pending_actions: int
