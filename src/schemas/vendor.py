from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, model_validator, validator
from datetime import date, datetime

from sqlmodel import SQLModel

from models.vendor import VendorProfileEnum, VendorStatusEnum, VendorTypeEnum, OperationZoneEnum, AddressDocumentType
from schemas.branch import IdName, CountryIdName, StateIdName, DistrictIdName, CityIdName

# --- Bank Details Schemas ---

class VendorBankDetailsBase(BaseModel):
    bank_name: str
    ifsc_code: str
    account_number: str
    account_holder_name: str
    document: Optional[str] = None

class VendorBankDetailsCreate(VendorBankDetailsBase):
    pass

class VendorBankDetailsRead(VendorBankDetailsBase):
    id: UUID

    class Config:
        from_attributes = True

# --- Contact Person Schemas (Local - No vendor_id required) ---

class VendorContactPersonBase(BaseModel):
    name: str
    mobile: str
    email: EmailStr

class VendorContactPersonCreate(VendorContactPersonBase):
    id: Optional[UUID] = None  # Optional for updates

class VendorContactPersonRead(VendorContactPersonBase):
    id: UUID

    class Config:
        from_attributes = True

# --- Agreement Schemas (Local - No vendor_id required) ---

class VendorAgreementBase(BaseModel):
    start_date: date
    end_date: date
    agreement_document: Optional[str] = None

class VendorAgreementCreate(VendorAgreementBase):
    id: Optional[UUID] = None  # Optional for updates

class VendorAgreementRead(VendorAgreementBase):
    id: UUID

    class Config:
        from_attributes = True

# --- Vehicle Type Link Schema ---

class VehicleTypeLink(BaseModel):
    id: UUID
    name: str

# --- Address Schema ---

class AddressRead(BaseModel):
    pin_code: str
    location: str
    country: CountryIdName
    state: StateIdName
    district: DistrictIdName
    city: CityIdName

# --- Document Schema ---
class DocumentDetails(BaseModel):
    gst_number: Optional[str] = None
    gst_document: Optional[str] = None
    pan_number: Optional[str] = None
    pan_document: Optional[str] = None
    address_document_type: AddressDocumentType
    address_document: Optional[str] = None

# --- Vendor Schemas ---

class VendorBase(BaseModel):
    vendor_name: str
    vendor_type: VendorTypeEnum
    vendor_profile: Optional[VendorProfileEnum] = None
  
    origin: Optional[str] = None
    destination: Optional[str] = None
    credit_period: int = 0
    operation_zone: Optional[OperationZoneEnum] = None
    route: Optional[str] = None
    status: VendorStatusEnum = VendorStatusEnum.PENDING
   
    reject_reason: Optional[str] = None 
    @validator('operation_zone', pre=True)
    def check_operation_zone(cls, v):
        if v not in [item.value for item in OperationZoneEnum]:
            return None
        return v


class VendorCreate(BaseModel):
    vendor_name: str
    vendor_type: VendorTypeEnum
    registration_id: UUID
    branch_id: UUID
    pin_code: str
    location: str
    address_document_type: AddressDocumentType
    vendor_profile: Optional[VendorProfileEnum] = None
    gst_number: str
    pan_number: str
    origin_id: Optional[UUID] = None  
    destination_id: Optional[UUID] = None  
    credit_period: int = 0
    operation_zone: Optional[OperationZoneEnum] = None
    route: Optional[str] = None
    bank_details: VendorBankDetailsCreate
    contact_persons: List[VendorContactPersonCreate] 
    agreements: List[VendorAgreementCreate] 
    vehicle_type_ids: List[UUID]
    country_id: Optional[UUID] = None
    state_id: Optional[UUID] = None
    district_id: Optional[UUID] = None
    city_id: Optional[UUID] = None

    @model_validator(mode='before')
    def check_vendor_type_requirements(cls, values):
        vendor_type = values.get('vendor_type')
        if vendor_type == VendorTypeEnum.CREDIT_VENDOR:
            if not all([values.get('origin_id'), values.get('destination_id')]):
                raise ValueError('origin and destination are required for credit vendors')
            values['vendor_profile'] = None
            values['operation_zone'] = None
            values['route'] = None
        elif vendor_type == VendorTypeEnum.ADVANCE_VENDOR:
            if not all([values.get('vendor_profile')]):
                raise ValueError('vendor_profile is required for advance vendors')
            values['origin_id'] = None  
            values['destination_id'] = None  
        return values
    @validator('contact_persons')
    def validate_contact_persons(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one contact person is required")
        return v
    
    @validator('agreements')
    def validate_agreements(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one agreement is required")
        return v
    @validator('vehicle_type_ids')
    def validate_vehicle_type_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one vehicle type is required")
        return v

class VendorUpdate(BaseModel):
    vendor_name: Optional[str] = None
    vendor_type: Optional[VendorTypeEnum] = None
    vendor_profile: Optional[VendorProfileEnum] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    origin_id: Optional[UUID] = None  
    destination_id: Optional[UUID] = None 
    credit_period: Optional[int] = None
    operation_zone: Optional[OperationZoneEnum] = None
    route: Optional[str] = None
    address_document_type: Optional[AddressDocumentType] = None
    pin_code: Optional[str] = None
    location: Optional[str] = None
    country_id: Optional[UUID] = None
    state_id: Optional[UUID] = None
    district_id: Optional[UUID] = None
    city_id: Optional[UUID] = None
    bank_details: Optional[VendorBankDetailsCreate] = None
    contact_persons: Optional[List[VendorContactPersonCreate]] = None
    agreements: Optional[List[VendorAgreementCreate]] = None
    vehicle_type_ids: Optional[List[UUID]] = None


class VendorStatusUpdate(BaseModel):
    status: VendorStatusEnum
    reject_reason: Optional[str] = None
    
    @validator('reject_reason')
    def validate_reject_reason(cls, v, values):
        if values.get('status') == VendorStatusEnum.REJECTED:
            if not v or v.strip() == "":
                raise ValueError("Reject reason is required when status is REJECTED")
        return v


class VendorRead(VendorBase):
    id: UUID
    vendor_code: str
    branch: IdName
    address: AddressRead
    documents: DocumentDetails 
    vehicle_types: List[VehicleTypeLink] = []
    contact_persons: List[VendorContactPersonRead]
    agreements: List[VendorAgreementRead]
    bank_details: List[VendorBankDetailsRead]
    origin: Optional[CityIdName] = None 
    destination: Optional[CityIdName] = None
    is_active: bool 
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    approved_by: Optional[str] = None 

    class Config:
        from_attributes = True

class VendorStatistics(BaseModel):
    total: int
    approved: int
    pending: int
    rejected: int


class VendorListRead(SQLModel):
    id: UUID
    vendor_name: str
    vendor_code: str
    vendor_type: str
    branch: IdName
    region:str
    address: dict
    is_active: bool 
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None


class VendorList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    statistics : VendorStatistics
    results: List[VendorListRead] = []


class VendoropenList(BaseModel):
    total: int
  
    statistics : VendorStatistics
    results: List[VendorListRead] = []


class VendorDetails(BaseModel):
    id: UUID
    vendor_code: str
    vendor_name: str
    vendor_type: VendorTypeEnum
    vendor_profile: Optional[VendorProfileEnum]
    branch: IdName
    address: AddressRead

    class Config:
        from_attributes = True
        
        
class VendorDuplicateCheck(BaseModel):
    gst_duplicate: bool
    pan_duplicate: bool
    gst_vendor: Optional[dict] = None
    pan_vendor: Optional[dict] = None


class VendorCreditPeriodUpdate(BaseModel):
    """Update vendor credit period only"""
    credit_period: int


class VendorBankDetailsUpdate(BaseModel):
    """Update vendor bank details"""
    bank_name: str
    account_number: str
    ifsc_code: str
    
    account_holder_name: str