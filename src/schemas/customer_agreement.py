
from uuid import UUID
from pydantic import BaseModel
from datetime import date

class CustomerAgreementBase(BaseModel):
    start_date: date
    end_date: date
    customer_id: UUID

class CustomerAgreementCreate(CustomerAgreementBase):
    pass

class CustomerAgreementUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

class CustomerAgreementRead(CustomerAgreementBase):
    id: UUID
    agreement_document: str
    class Config:
        from_attributes = True


class CustomerAgreementList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[CustomerAgreementRead] = []
