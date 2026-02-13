from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import List, Optional
import enum
from models.vendor_registation import VendorRegistrationStatusEnum
from .branch import IdName, AddressCreate, AddressRead

class VehicleTypeLink(BaseModel):
    id: UUID
    name: str

class VendorRegistrationBase(BaseModel):
    transporter_firm_name: str
    owner_name: str
    contact_number: str
    gst_number: Optional[str] = None
    gst_document: Optional[str] = None
    pan_card_number: Optional[str] = None
    pan_card_document: Optional[str] = None
    region_id: UUID
    total_vehicle_owned: int
    route: str
    visiting_card: Optional[str] = None

class VendorRegistrationCreate(VendorRegistrationBase):
    address: AddressCreate
    vehicle_type_ids: List[UUID]

class VendorRegistrationUpdate(VendorRegistrationBase):
    transporter_firm_name: Optional[str] = None
    owner_name: Optional[str] = None
    contact_number: Optional[str] = None
    region_id: Optional[UUID] = None
    total_vehicle_owned: Optional[int] = None
    route: Optional[str] = None
    address: Optional[AddressCreate] = None
    vehicle_type_ids: Optional[List[UUID]] = None

class VendorRegistrationRead(VendorRegistrationBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None
    address: AddressRead
    region: IdName
    vehicle_types: List[VehicleTypeLink]
    status: VendorRegistrationStatusEnum

    class Config:
        from_attributes = True

class VendorRegistrationStatusUpdate(BaseModel):
    status: VendorRegistrationStatusEnum

class VendorRegistrationList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[VendorRegistrationRead] = []


class DuplicateCheckType(str, enum.Enum):
    GST = "gst"
    PAN = "pan"

class DuplicateCheckRequest(BaseModel):
    type: DuplicateCheckType
    number: str

class DuplicateCheckResponse(BaseModel):
    is_available: bool
    message: str
