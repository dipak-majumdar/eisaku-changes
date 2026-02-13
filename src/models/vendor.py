from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Field, Relationship, Session
from db.base import BaseTable
import enum
from utils.get_region import get_region_data

# --- Enums for Vendor Model ---

class VendorTypeEnum(str, enum.Enum):
    CREDIT_VENDOR = "Credit"
    ADVANCE_VENDOR = "Advance"

class VendorProfileEnum(str, enum.Enum):
    BROKER = "Broker"
    FLEET_OWNER = "Fleet Owner"

class VendorStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class OperationZoneEnum(str, enum.Enum):
    ALL_INDIA = "All India"
    ROUTE_SPECIFIC = "Route Specific"

class AddressDocumentType(str, enum.Enum):
   AADHAR_CARD = "Aadhar Card"
   VOTER_CARD = "Voter Card"
   VISITING_CARD = "Visiting Card"
   DRIVING_LICENSE = "Driving License"


# --- Type Checking Imports ---

if TYPE_CHECKING:
    from .vendor_registation import VendorRegistration
    from .branch import Branch
    from .vehicle_type import VehicleType
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .user import User


# --- Link Table for Many-to-Many Relationship ---

class VendorVehicleLink(BaseTable, table=True):
    __tablename__ = "marketline_vendor_vehicle_link"

    vendor_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vendors.id", primary_key=True)
    vehicle_type_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vehicle_types.id", primary_key=True)


# --- Main Vendor Model ---

class Vendor(BaseTable, table=True):
    __tablename__ = "marketline_vendors"

    vendor_code: str = Field(nullable=False, unique=True, max_length=20)
    vendor_name: str = Field(nullable=False, max_length=255)
    
    registration_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vendor_registrations.id")
    branch_id: UUID = Field(foreign_key="marketline_branches.id")
    vendor_type: VendorTypeEnum = Field(nullable=False)
    vendor_profile: Optional[VendorProfileEnum] = Field(nullable=True)
    
    gst_number: Optional[str] = Field(default=None, max_length=50, unique=True)
    gst_document: Optional[str] = Field(default=None, max_length=255)
    pan_number: Optional[str] = Field(default=None, max_length=50, unique=True)
    pan_document: Optional[str] = Field(default=None, max_length=255)
    
    country_id: UUID = Field(foreign_key="marketline_countries.id")
    state_id: UUID = Field(foreign_key="marketline_states.id")
    district_id: UUID = Field(foreign_key="marketline_districts.id")
    city_id: UUID = Field(foreign_key="marketline_cities.id")
    pin_code: str = Field(max_length=20)
    location: str = Field(max_length=255)
    address_document: Optional[str] = Field(default=None, max_length=255)
    address_document_type: AddressDocumentType = Field(nullable=False)

    origin_id: Optional[UUID] = Field(default=None, foreign_key="marketline_cities.id")
    destination_id: Optional[UUID] = Field(default=None, foreign_key="marketline_cities.id")
    
    credit_period: int = Field(default=0)
    
    operation_zone: Optional[OperationZoneEnum] = Field(default=None)
    route: Optional[str] = Field(default=None, max_length=255)
    
    status: VendorStatusEnum = Field(default=VendorStatusEnum.PENDING)
    reject_reason: Optional[str] = Field(default=None, max_length=500)
    user_id: Optional[UUID] = Field(default=None, foreign_key="marketline_users.id")

    # Relationships
    user: Optional["User"] = Relationship()
    branch: "Branch" = Relationship(back_populates="vendors")
    country: "Country" = Relationship()
    state: "State" = Relationship()
    district: "District" = Relationship()
    city: "City" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Vendor.city_id]",
            "primaryjoin": "Vendor.city_id == City.id"
        }
    )
    origin: Optional["City"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Vendor.origin_id]",
            "primaryjoin": "Vendor.origin_id == City.id"
        }
    )
    destination: Optional["City"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Vendor.destination_id]",
            "primaryjoin": "Vendor.destination_id == City.id"
        }
    )

    
    contact_persons: List["VendorContactPerson"] = Relationship(sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    agreements: List["VendorAgreement"] = Relationship(sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    bank_details: List["VendorBankDetails"] = Relationship(sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    
    vehicle_types: List["VehicleType"] = Relationship(link_model=VendorVehicleLink)

    @property
    def address(self) -> dict:
        """Return a combined address block."""
        return {
            "country": getattr(self.country, "name", None),
            "state": getattr(self.state, "name", None),
            "district": getattr(self.district, "name", None),
            "city": getattr(self.city, "name", None),
            "pin_code": self.pin_code,
            "location": self.location,
        }
    @property
    def balance(self) -> Decimal:
        """
        Calculate vendor balance from trips.
        Balance = Sum(trip_rate + other_charges + other_unloading_charges) - Sum(advance)
        Only count advance if trip.is_advance_given = True
        """
        from models.trip import TripVendor
        from sqlalchemy import func
        from sqlalchemy.exc import MissingGreenlet
        
        try:
            session = Session.object_session(self)
            # Safety check for async session
            if not session or not hasattr(session, 'query'):
                return Decimal("0.00")
            
            # Get all trip vendors for this vendor
            trip_vendors = session.query(TripVendor).filter(
                TripVendor.vendor_id == self.id
            ).all()
            
            total_charges = Decimal("0.00")
            total_advance = Decimal("0.00")
            
            for tv in trip_vendors:
                # Add: trip_rate + other_charges + other_unloading_charges
                total_charges += tv.trip_rate
                total_charges += tv.other_charges
                total_charges += tv.other_unloading_charges
                
                # Subtract: advance (only if trip.is_advance_given = True)
                if tv.trip and tv.trip.is_advance_given:
                    total_advance += tv.advance
            
            balance = total_charges - total_advance
            return balance
        except (MissingGreenlet, AttributeError):
            # Return 0 if accessed in async context
            return Decimal("0.00")    
    @property
    def region(self) -> str:
        region_map = get_region_data()
        if not self.state or not self.state.name:
            return ""
        region_name = region_map.get(self.state.name.lower())
        return region_name or ""


# --- Child Tables for Vendor ---

class VendorContactPerson(BaseTable, table=True):
    __tablename__ = "marketline_vendor_contact_persons"

    vendor_id: UUID = Field(foreign_key="marketline_vendors.id")
    name: str = Field(max_length=255)
    mobile: str = Field(max_length=20)
    email: str = Field(max_length=255)

    vendor: "Vendor" = Relationship()


class VendorAgreement(BaseTable, table=True):
    __tablename__ = "marketline_vendor_agreements"

    vendor_id: UUID = Field(foreign_key="marketline_vendors.id")
    start_date: date
    end_date: date
    agreement_document: str = Field(max_length=255)
    vendor: "Vendor" = Relationship()


class VendorBankDetails(BaseTable, table=True):
    __tablename__ = "marketline_vendor_bank_details"

    vendor_id: UUID = Field(foreign_key="marketline_vendors.id")
    bank_name: str = Field(max_length=255)
    ifsc_code: str = Field(max_length=20)
    account_number: str = Field(max_length=50, unique=True)
    account_holder_name: str = Field(max_length=255)
    document: Optional[str] = Field(default=None, max_length=255)

    vendor: "Vendor" = Relationship()
