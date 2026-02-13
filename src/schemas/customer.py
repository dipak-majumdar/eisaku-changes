from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, validator
from datetime import date, datetime
import re
from sqlmodel import SQLModel

from models.customer import CustomerTypeEnum, CustomerStatusEnum, CustomerAddressDocumentType, PaymentTerm
from schemas.branch import IdName, CountryIdName, StateIdName, DistrictIdName, CityIdName

# --- Contact Person Schemas ---

class CustomerContactPersonBase(BaseModel):
    name: str
    mobile: str
    email: EmailStr

class CustomerContactPersonCreate(CustomerContactPersonBase):
    pass

class CustomerContactPersonRead(CustomerContactPersonBase):
    id: UUID

    class Config:
        from_attributes = True

# --- Agreement Schemas ---

class CustomerAgreementBase(BaseModel):
    start_date: date
    end_date: date
    agreement_document: Optional[str] = None

class CustomerAgreementCreate(CustomerAgreementBase):
    pass

class CustomerAgreementRead(CustomerAgreementBase):
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
    gst_number: str
    gst_document: str
    pan_number: str
    pan_document: str
    address_document_type: CustomerAddressDocumentType
    address_document: str

# --- Customer Schemas ---

class CustomerBase(BaseModel):
    customer_name: str
    customer_type: CustomerTypeEnum
   
  
    tonnage: Optional[str] = None
    trip_rate: Optional[str] = None
    credit_period: int = 0
    status: CustomerStatusEnum = CustomerStatusEnum.PENDING
  
    payment_term: Optional[PaymentTerm]=None
    reject_reason: Optional[str] = None
    

class CustomerCreate(BaseModel):
    customer_name: str
    customer_type: CustomerTypeEnum
    pin_code: str
    location: str
    country_id: UUID
    state_id: UUID
    district_id: UUID
    city_id: UUID
    address_document_type: CustomerAddressDocumentType
    payment_term: Optional[PaymentTerm] = None
    vehicle_type_id: Optional[UUID] = None
      # ✅ NEW: User credentials
    mobile: str
    email: Optional[str] = None
    password: str
    gst_number: str
    pan_number: str
    origin_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    tonnage: Optional[str] = None
    trip_rate: Optional[str] = None
    credit_period: int = 0
    contact_persons: List[CustomerContactPersonCreate]
    agreements: List[CustomerAgreementCreate]

    @validator('gst_number')
    def validate_gst_number(cls, v):
        if v and not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", v):
            raise ValueError("Invalid GST number")
        return v
    @validator('pan_number')
    def validate_pan_number(cls, v):
        if v and not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", v):
            raise ValueError("Invalid PAN number")
        return v
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


class CustomerUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_type: Optional[CustomerTypeEnum] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    origin_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    tonnage: Optional[str] = None
    trip_rate: Optional[str] = None
    credit_period: Optional[int] = None
    address_document_type: Optional[CustomerAddressDocumentType] = None
    pin_code: Optional[str] = None
    location: Optional[str] = None
    country_id: Optional[UUID] = None
    state_id: Optional[UUID] = None
    district_id: Optional[UUID] = None
    city_id: Optional[UUID] = None
    contact_persons: Optional[List[CustomerContactPersonCreate]] = None
    agreements: Optional[List[CustomerAgreementCreate]] = None
    vehicle_type_id: Optional[UUID] = None
    payment_term: Optional[PaymentTerm] = None
    
class CustomerStatusUpdate(BaseModel):
    status: CustomerStatusEnum
    reject_reason: Optional[str] = None  
    
    @validator('reject_reason')
    def validate_reject_reason(cls, v, values):
        # Check if status is REJECTED and reject_reason is missing
        if values.get('status') == CustomerStatusEnum.REJECTED:
            if not v or v.strip() == "":
                raise ValueError("Reject reason is required when status is REJECTED")
        return v


class CustomerRead(CustomerBase):
    id: UUID
    customer_code: str
    address: AddressRead
    documents: DocumentDetails
    vehicle_type: Optional[VehicleTypeLink] = None  
    contact_persons: List[CustomerContactPersonRead]
    agreements: List[CustomerAgreementRead]
    origin: Optional[CityIdName] = None  
    destination: Optional[CityIdName] = None
    mobile: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    approved_by: Optional[str] = None  
    class Config:
        from_attributes = True

class CustomerListRead(SQLModel):
    id: UUID
    customer_name: str
    customer_code: str
    customer_type: str
    vehicle_type: Optional[IdName] = None 
    address: dict
    region:str
    is_active: bool
    status: str
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    class Config:
        from_attributes = True



class CustomerDetails(BaseModel):
    id: UUID
    customer_code: str
    customer_name: str
    customer_type: CustomerTypeEnum
    address: AddressRead
    is_active: bool
    class Config:
        from_attributes = True
        
        

class CustomerDuplicateCheck(BaseModel):
    gst_duplicate: bool
    pan_duplicate: bool
    gst_customer: Optional[dict] = None
    pan_customer: Optional[dict] = None



class CustomerStatistics(BaseModel):
    """Customer statistics"""
    total: int
    approved: int
    pending: int
    rejected: int


class CustomerList(BaseModel):
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    statistics: CustomerStatistics
    results: List[CustomerListRead]


class ApprovedCustomerRead(BaseModel):
    id: UUID
    name: str
    code: str
    address: dict
    type: CustomerTypeEnum
    mobile: str  # ✅ ADDED
    email: Optional[str] = None  # ✅ ADDED
    created_at: datetime
    status: CustomerStatusEnum

    # avatar: str


class ApprovedCustomerList(BaseModel):
    results: List[ApprovedCustomerRead]