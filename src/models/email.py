from datetime import datetime
from typing import Optional
from sqlmodel import Field
from db.base import BaseTable


class Email(BaseTable, table=True):
    __tablename__ = "marketline_emails"

    subject: str = Field(max_length=255)
    body: str = Field()
    recipient_email: str = Field(max_length=255)
    status: str = Field(max_length=50, default="pending")  # e.g., pending, sent, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)