from pydantic import BaseModel, validator, Field as PydanticField
from datetime import date, datetime, timedelta
from uuid import UUID
from typing import List, Optional
from decimal import Decimal

from models.trip import TripStatusEnum, GoodsTypeEnum, AddressTypeEnum



class AddressCreate(BaseModel):
    """Address with FK references to Country/State/District/City"""
    # id: Optional[UUID] = None  # For identifying existing addresses on update
    state_id: UUID
    district_id: UUID
    city_id: UUID
    location: str
    pincode: str

    # @validator('id', pre=True)
    # def empty_str_to_none(cls, v):
    #     if v == "":
    #         return None
    #     return v

class AddressUpdate(BaseModel):
    """Address with FK references to Country/State/District/City"""
    id: Optional[UUID] = None  # For identifying existing addresses on update
    state_id: UUID
    district_id: UUID
    city_id: UUID
    location: str
    pincode: str

    @validator('id', pre=True)
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

class AddressRead(BaseModel):
    """Address response with nested names"""
    id: UUID
    address_type: AddressTypeEnum
    country: "IdName"
    state: "IdName"
    district: "IdName"
    city: "IdName"
    location: str
    pincode: str
    
    class Config:
        from_attributes = True

class MinimalAddressLoad(BaseModel):
    """Address response in minimal format """
    address_type: AddressTypeEnum
    country: str = ""
    state: str = ""
    district: str = ""
    city: str = ""
    location: str = ""
    pincode: str = ""
    
    class Config:
        from_attributes = True


class AddressList(BaseModel):
    """Address response with nested names"""
    id: UUID
    address_type: AddressTypeEnum
    country: "IdName"
    state: "IdName"
    district: "IdName"
    city: "IdName"
    location: str
    pincode: str
    
    class Config:
        from_attributes = True

class IdNameCode(BaseModel):
    """Enhanced object with id, name, and code"""
    id: UUID
    name: str
    code: str  
    type: str
    
    class Config:
        from_attributes = True


class IdName(BaseModel):
    id: UUID
    name: str
    
    class Config:
        from_attributes = True


# --- Trip Base Schema ---
class TripBase(BaseModel):
    trip_date: date
    # status: TripStatusEnum = TripStatusEnum.PENDING
    capacity: int
    goods_type: GoodsTypeEnum
    goods_name: Optional[str] = None
    trip_rate: Decimal
    loading_unloading_charges: Decimal = Decimal("0.00")
    late_fine: Decimal = Decimal("0.00")
    instructions: Optional[str] = None

   


# --- Trip Create Schema (Form-compatible) ---
class TripCreate(TripBase):
    """Create trip with multiple addresses (Form-compatible)"""
    customer_id: UUID
    vehicle_type_id: UUID
    
    loading_addresses: List[AddressCreate] = PydanticField(..., alias="loading_addresses")
    unloading_addresses: List[AddressCreate] = PydanticField(..., alias="unloading_addresses")
    
    @validator('goods_name')
    def validate_goods_name(cls, v, values):
        goods_type = values.get('goods_type')
        if goods_type == GoodsTypeEnum.OTHER and not v:
            raise ValueError('goods_name is required when goods_type is OTHER')
        return v
    
    @validator('trip_date')
    def validate_trip_date(cls, v: date):
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        # Allow future dates. Only restrict dates that are older than 7 days in the past.
        if v < seven_days_ago:
            raise ValueError("Trip date must be within the last 7 days (past). Future dates are allowed.")
        return v


# --- Trip Update Schema ---
class TripUpdate(TripBase):
    """Update trip (all fields required)"""
    customer_id: UUID
    vehicle_type_id: UUID
    loading_addresses_json: List[AddressUpdate] = PydanticField(..., alias="loading_addresses")
    unloading_addresses_json: List[AddressUpdate] = PydanticField(..., alias="unloading_addresses")

class TripStatusUpdate(BaseModel):
    """Schema for updating only the trip status."""
    status: TripStatusEnum
    remarks: Optional[str] = None

    @validator('remarks')
    def validate_remarks_for_rejected(cls, v, values):
        if values.get('status') == TripStatusEnum.REJECTED and (v is None or v.strip() == ""):
            raise ValueError("Remarks are required when the status is REJECTED.")
        return v

class StatusHistoryRead(BaseModel):
    previous_status: Optional[TripStatusEnum] = None
    current_status: TripStatusEnum
    updated_at: datetime
    updated_by: Optional[UUID] = None
    remarks: Optional[str] = None

# --- Trip Read Schema ---
class TripVendorRead(BaseModel):
    """Schema for reading assigned vendor details."""
    id: UUID
    vendor: "VendorWithAddress"
    vehicle_type: IdName
    tons: int
    vehicle_no: str
    insurance_expiry_date: Optional[date] = None
    rc_copy: Optional[str] = None
    insurance_copy: Optional[str] = None
    drivers: List["TripDriverRead"] = []
    trip_rate: Decimal
    advance: Decimal
    other_charges: Decimal
    other_unloading_charges: Decimal
    balance: Optional[Decimal] = None
    

    class Config:
        from_attributes = True


class TripDriverRead(BaseModel):
    """Schema for reading driver details."""
    id: UUID
    driver_name: str
    driver_mobile_no: str
    driver_licence_no: str
    driver_licence_expiry: date

    class Config:
        from_attributes = True


class TripVendorAssign(BaseModel):
    """Schema for assigning a vendor to a trip via raw JSON."""
    branch_id: UUID
    vendor_id: UUID

    vehicle_type_id: UUID
    tons: int
    vehicle_no: str
    insurance_expiry_date: date

    drivers: List["TripDriverCreate"]
    trip_rate: Decimal
    advance: Decimal
    other_charges: Decimal = Decimal("0.00")


class TripDriverCreate(BaseModel):
    """Schema for creating a driver for a trip."""
    driver_name: str
    driver_mobile_no: str
    driver_licence_no: str
    driver_licence_expiry: date
    
class VehicleLoadingDocumentRead(BaseModel):
    """Schema for reading trip document details."""
    id: UUID
    eway_bill: str
    invoice_copy: str
    vehicle_image: str
    lr_copy: str
    pod_submit: str
    comments: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True




class TripDocumentRead(BaseModel):
    """Schema for reading trip document details."""
    id: UUID
    eway_bill: str
    invoice_copy: str
    vehicle_image: str
    lr_copy: str
    pod_submitted: Optional[bool] = None
    other_charges: Optional[Decimal] = None
    is_shortage: Optional[bool] = None
    is_damage: Optional[bool] = None
    comments: Optional[str] = None
    deducted_amount: Optional[Decimal] = None
    deducted_details: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True



class TripListDetails(TripBase):
    id: UUID
    trip_code: str
    status: TripStatusEnum = TripStatusEnum.PENDING

    
    # ✅ Nested relationships
    # branch: IdName
    customer: IdNameCode
    vehicle_type: IdName
    
    # ✅ Addresses with full details
    loading_addresses: List[AddressRead]
    unloading_addresses: List[AddressRead]
    # status_history: List[StatusHistoryRead] = []
    # assigned_vendor: Optional[TripVendorRead] = None
    
    # Audit fields
    is_active: bool
    # created_at: datetime
    # updated_at: datetime
    # created_by: Optional[UUID] = None
    # updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            Decimal: str
        }


class TripMinimal(BaseModel):
    """Minimal trip data for fast listing"""
    id: UUID
    customer: IdNameCode
    trip_code: str
    trip_date: date
    status: TripStatusEnum = TripStatusEnum.PENDING

    loading_addresses: List[MinimalAddressLoad]
    unloading_addresses: List[MinimalAddressLoad]
    
    class Config:
        from_attributes = True



class CustomerWithAddressIds(IdNameCode):
    """Customer details including address IDs and location."""
    address: dict

    class Config:
        from_attributes = True


class VendorWithAddress(IdName):
    """Vendor details including address IDs and location."""
    code: str
    type: str
    address: dict

    class Config:
        from_attributes = True

class TripRead(TripBase):
    id: UUID
    trip_code: str
    cancellation_reason: Optional[str] = None
    status: Optional[TripStatusEnum] = None


    can_approve_role: Optional[str] = None
    is_shortage: Optional[bool] = False
    is_damage: Optional[bool] = False
    deducted_amount: Optional[Decimal] = None
    deducted_details: Optional[str] = None
    advance_approval: Optional[bool] = False
    balance_approval: Optional[bool] = False
    can_view_fleet_rate: Optional[bool] = False
    
    # ✅ Nested relationships
    # branch: IdName
    branch: "BranchWithAddress"
    # customer: IdNameCode
    customer: "CustomerWithAddressIds"

    vehicle_type: IdName
    pod_sent_to_customer: Optional[bool] = False
    
    # ✅ Addresses with full details
    loading_addresses: List[AddressRead]
    unloading_addresses: List[AddressRead]
    status_history: List[StatusHistoryRead] = []
    assigned_vendor: Optional[TripVendorRead] = None
    vehicle_loading_unloading_documents: Optional[VehicleLoadingDocumentRead] = None
    
    # Audit fields
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            Decimal: str
        }

class BranchWithAddress(IdName):
    """Branch details including code and address."""
    code: str
    address: dict

    class Config:
        from_attributes = True




# --- Trip Statistics ---
class TripStatistics(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    rejected: int


# --- Trip List Schema ---
class TripList(BaseModel):
    total: int
    statistics: TripStatistics
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[TripListDetails] = []

class TripMinimalList(BaseModel):
    """Minimal trip list response"""
    total: int
    statistics: TripStatistics
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[TripMinimal] = []


class PendingPODTripVendor(BaseModel):
    """Minimal vendor details for POD tracking"""
    id: UUID
    vendor_name: str
    vendor_code: str
    vehicle_no: str
    driver_name: str
    driver_mobile_no: str
    
    class Config:
        from_attributes = True

class PendingPODTrip(BaseModel):
    """Schema for trips pending POD submission"""
    id: UUID
    trip_code: str
    trip_date: date
    status: TripStatusEnum
    
    assigned_vendor: Optional[PendingPODTripVendor] = None
    
    vehicle_unloaded_date: Optional[date] = None
    pod_submission_last_date: Optional[date] = None
    pod_submitted_date: Optional[date] = None
    pod_overdue_days: int = 0
    pod_penalty_amount: Decimal = Decimal("0.00")
    
    class Config:
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            Decimal: str
        }

class PendingPODTripList(BaseModel):
    """List of trips pending POD submission"""
    total: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[PendingPODTrip] = []