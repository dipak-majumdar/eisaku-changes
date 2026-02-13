
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class ContactPersonBase(BaseModel):
	name: str
	mobile: str
	email: str
	vendor_id: UUID

class ContactPersonCreate(ContactPersonBase):
	pass

class ContactPersonUpdate(BaseModel):
	name: str | None = None
	mobile: str | None = None
	email: str | None = None

class ContactPersonRead(ContactPersonBase):
	id: UUID
	created_at: datetime
	updated_at: datetime
	created_by: UUID | None = None
	updated_by: UUID | None = None

	class Config:
		from_attributes = True

class ContactPersonList(BaseModel):
	total: int
	next: str | None = None
	previous: str | None = None
	results: list[ContactPersonRead] = []
