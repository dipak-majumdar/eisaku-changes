from uuid import UUID
from sqlmodel import Field, Relationship, SQLModel
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Text
from db.base import BaseTable

if TYPE_CHECKING:
    from .user import User

class Notification(BaseTable, table=True):
    __tablename__ = 'marketline_notifications'
    
    user_ids: Optional[str] = Field(default=None, sa_type=Text)  # JSON array of user IDs for bulk notifications
    role: Optional[str] = Field(default=None, max_length=50)
    notification_type: str = Field(max_length=50, nullable=False) 
    message: str = Field(max_length=500, nullable=False)
    
    
    # Action buttons support (new features)
    action_required: bool = Field(default=False)
    action_data: Optional[str] = Field(default=None, sa_type=Text)  # JSON data for action handling
    action_deadline: Optional[datetime] = Field(default=None)
    
    # Status
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = Field(default=None)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": "123e4567-e89b-12d3-a456-426614174000",
                "role": "admin",
                "notification_type": "trip_approval",
                "message": "Trip TRP000001 Created!",
                "action_required": True,
                "action_data": {
                    "buttons": [
                        {"name": "approve", "url": "/trips/approve"},
                        {"name": "reject", "url": "/trips/reject"}
                    ],
                    "redirect_url": "/trips",
                },
                "action_deadline": "2024-01-15T10:30:00Z",
                "is_read": False
            }
        }