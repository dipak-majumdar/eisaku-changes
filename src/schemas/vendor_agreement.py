
from uuid import UUID
from pydantic import BaseModel
from datetime import date

class VendorAgreementBase(BaseModel):
    start_date: date
    end_date: date
    vendor_id: UUID

class VendorAgreementCreate(VendorAgreementBase):
    pass

class VendorAgreementUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

class VendorAgreementRead(VendorAgreementBase):
    id: UUID
    agreement_document: str
    class Config:
        from_attributes = True


class VendorAgreementList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[VendorAgreementRead] = []
