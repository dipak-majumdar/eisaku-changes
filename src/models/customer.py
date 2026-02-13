from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Field, Relationship, Session
from db.base import BaseTable
import enum

from utils.get_region import get_region_data
from .vendor import AddressDocumentType


if TYPE_CHECKING:
   
    from .vehicle_type import VehicleType
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .user import User
    
class CustomerTypeEnum(str, enum.Enum):
    BROKING = "Broking"
    BOOKING = "Booking"
    
    
class CustomerStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    
class CustomerAddressDocumentType(str, enum.Enum):
   AADHAR_CARD = "Aadhar Card"
   VOTER_CARD = "Voter Card"
   VISITING_CARD = "Visiting Card"
   DRIVING_LICENSE = "Driving License"



import sqlalchemy as sa

class PaymentTerm(str, enum.Enum):
    ADVANCE = "Advance"
    CREDIT = "Credit"


class Customer(BaseTable, table=True):
    __tablename__ = "marketline_customers"

    customer_code: str = Field(nullable=False, unique=True, max_length=20)
    customer_name: str = Field(nullable=False, max_length=255)
    

    customer_type: CustomerTypeEnum = Field(nullable=False)
    status: CustomerStatusEnum = Field(default=CustomerStatusEnum.PENDING)
    user_id: Optional[UUID] = Field(default=None, foreign_key="marketline_users.id")
    
    gst_number: str = Field(nullable=False, max_length=50, unique=True) 
    gst_document: str = Field(max_length=255)
    pan_number: str = Field(nullable=False, max_length=50, unique=True)
    pan_document: str = Field(max_length=255)
    mobile: str = Field(nullable=False, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=255)
    country_id: UUID = Field(foreign_key="marketline_countries.id")
    state_id: UUID = Field(foreign_key="marketline_states.id")
    district_id: UUID = Field(foreign_key="marketline_districts.id")
    city_id: UUID = Field(foreign_key="marketline_cities.id")
    pin_code: str = Field(max_length=20)
    location: str = Field(max_length=255)
    address_document: str = Field(max_length=255)
    address_document_type: AddressDocumentType = Field(nullable=False)

    origin_id: Optional[UUID] = Field(default=None, foreign_key="marketline_cities.id")
    destination_id: Optional[UUID] = Field(default=None, foreign_key="marketline_cities.id")
    tonnage : Optional[str] = Field(default=None, max_length=255)
    trip_rate : Optional[str] = Field(default=None, max_length=255)

    credit_period: int = Field(default=0)
    payment_term: Optional[PaymentTerm] = Field(default=None, sa_column=sa.Column(sa.Enum(PaymentTerm), nullable=True)) 
    
    vehicle_type_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vehicle_types.id")
    reject_reason: Optional[str] = Field(default=None, max_length=500)
    #relation
    user: Optional["User"] = Relationship()
   
    country: "Country" = Relationship()
    state: "State" = Relationship()
    district: "District" = Relationship()
    city: "City" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.city_id]"})
    origin: Optional["City"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.origin_id]"})
    destination: Optional["City"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Customer.destination_id]"})
    
    contact_persons: List["CustomerContactPerson"] = Relationship(sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    agreements: List["CustomerAgreement"] = Relationship(sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    
    vehicle_type: Optional["VehicleType"] = Relationship()
    

    @property
    def address(self) -> dict:
        """Return a combined address block."""
        return {
            "country": getattr(self.country, "name", None),
            "state": getattr(self.state, "name", None),
            "district": getattr(self.district, "name", None),
            "city": getattr(self.city, "name", None),
            "pincode": self.pin_code,
            "location": self.location,
        }
    @property
    def balance(self) -> Decimal:
        """
        Calculate customer balance from trips.
        Balance = Sum(trip_rate + loading_unloading_charges) - Sum(deducted_amount)
        """
        from models.trip import Trip
        from sqlalchemy import func
        from sqlalchemy.exc import MissingGreenlet
        
        try:
            session = Session.object_session(self)
            # Safety check for async session
            if not session or not hasattr(session, 'query'):
                return Decimal("0.00")
            
            # Get all trips for this customer
            trips = session.query(Trip).filter(
                Trip.customer_id == self.id
            ).all()
            
            total_charges = Decimal("0.00")
            total_deductions = Decimal("0.00")
            
            for trip in trips:
                # Add: trip_rate + loading_unloading_charges
                total_charges += trip.trip_rate
                total_charges += trip.loading_unloading_charges
                # Subtract: deducted_amount (if any)
                if trip.deducted_amount:
                    total_deductions += trip.deducted_amount
            
            balance = total_charges + total_deductions
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

class CustomerContactPerson(BaseTable, table=True):
    __tablename__ = "marketline_customer_contact_persons"

    customer_id: UUID = Field(foreign_key="marketline_customers.id")
    name: str = Field(max_length=255)
    mobile: str = Field(max_length=20)
    email: str = Field(max_length=255)

    customer: "Customer" = Relationship()


class CustomerAgreement(BaseTable, table=True):
    __tablename__ = "marketline_customer_agreements"

    customer_id: UUID = Field(foreign_key="marketline_customers.id")
    start_date: date
    end_date: date
    agreement_document: str = Field(max_length=255)
    customer: "Customer" = Relationship()