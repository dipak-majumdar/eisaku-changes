# models/trip.py

from typing import TYPE_CHECKING, Optional
from uuid import UUID
from datetime import date,timedelta
from decimal import Decimal
from sqlmodel import Field, Relationship, Column
from sqlalchemy import Numeric
from db.base import BaseTable
import enum, sqlalchemy as sa
 

if TYPE_CHECKING:
    from .branch import Branch
    from .customer import Customer
    from .vendor import Vendor
    from .vehicle_type import VehicleType
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .user import User


class TripStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"           # Trip Approved         # branch manager
    REJECTED = "Rejected"           # Trip Rejected         # branch manager
    
    VENDOR_ASSIGNED = "Vendor Assigned"
    DRIVER_ASSIGNED = "Driver Assigned"

    FLIT_RATE_APPROVE = "Flit Rate Approve"   
    FLIT_RATE_REJECT = "Flit Rate Reject"          # branch manager(> 5%) and management(<5%)
    
    FLEET_RATE_APPROVE = "Fleet Rate Approve"   
    FLEET_RATE_REJECT = "Fleet Rate Reject"   
    VEHICLE_LOADED = "Vehicle Loaded"
    VEHICLE_UNLOADED = "Vehicle Unloaded"

    # status no needed to store in DB
    # ADVANCE_PAYMENT_PENDING = "Advance Payment Pending"         # management
    # ADVANCE_PAYMENT_APPROVED = "Advance Payment Approved"
    # ADVANCE_PAYMENT_REJECTED = "Advance Payment Rejected"

    ADVANCE_PAYMENT = "Advance Payment"                         # Accounts

    POD_SUBMITTED = "POD Submitted"

    IN_TRANSIT = "In Transit"           
    COMPLETED = "Completed"


class GoodsTypeEnum(str, enum.Enum):
    FMCG = "FMCG"
    CHEMICAL = "Chemical"
    FASHION = "Fashion"
    ELECTRONICS = "Electronics"
    OTHER = "Other"

class AddressTypeEnum(str, enum.Enum):
    LOADING = "Loading"
    UNLOADING = "Unloading"
    
# ✅ Unified TripAddress table
class TripAddress(BaseTable, table=True):
    __tablename__ = "marketline_trip_addresses"
    
    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)
    address_type: AddressTypeEnum = Field(nullable=False)
    country_id: UUID = Field(foreign_key="marketline_countries.id", nullable=False)
    state_id: UUID = Field(foreign_key="marketline_states.id", nullable=False)
    district_id: UUID = Field(foreign_key="marketline_districts.id", nullable=False)
    city_id: UUID = Field(foreign_key="marketline_cities.id", nullable=False)
    location: str = Field(nullable=False, max_length=500)
    pincode: str = Field(nullable=False, max_length=10)
    sequence: int = Field(default=1, nullable=False)
    
    # Relationships
    trip: "Trip" = Relationship(back_populates="addresses")
    country: "Country" = Relationship()
    state: "State" = Relationship()
    district: "District" = Relationship()
    city: "City" = Relationship()

class TripStatusHistory(BaseTable, table=True): # type: ignore
    __tablename__ = "marketline_trip_status_history"
    
    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)
    
    previous_status: Optional[TripStatusEnum] = Field(
        default=None, sa_column=sa.Column(sa.Enum(TripStatusEnum, name="tripstatusenum", native_enum=False, length=100), nullable=True)
    )
    current_status: TripStatusEnum = Field(
        sa_column=sa.Column(sa.Enum(TripStatusEnum, name="tripstatusenum", native_enum=False, length=100), nullable=False)
    )
    remarks: Optional[str] = Field(default=None, max_length=500)
    
    # Relationships
    trip: "Trip" = Relationship(back_populates="status_history")
    changed_by_user: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[TripStatusHistory.updated_by]", "primaryjoin": "TripStatusHistory.updated_by == User.id"})


class Trip(BaseTable, table=True):
    __tablename__ = "marketline_trips"

    # Basic Info
    trip_code: str = Field(nullable=False, unique=True, max_length=20, index=True)
    trip_date: date = Field(nullable=False)
    status: TripStatusEnum = Field(
        default=TripStatusEnum.PENDING, sa_column=sa.Column(sa.Enum(TripStatusEnum, name="tripstatusenum", native_enum=False, length=100))
    )
    
    branch_id: UUID = Field(foreign_key="marketline_branches.id", nullable=False)
    customer_id: UUID = Field(foreign_key="marketline_customers.id", nullable=False)
    vehicle_type_id: UUID = Field(foreign_key="marketline_vehicle_types.id", nullable=False)
    
    # Vehicle Info
    capacity: int = Field(nullable=False)
  
    goods_type: GoodsTypeEnum = Field(nullable=False)
    goods_name: Optional[str] = Field(default=None, max_length=255)
    
    trip_rate: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    loading_unloading_charges: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(10, 2), nullable=False)
    )

    is_shortage: Optional[bool] = Field(default=False)
    is_damage: Optional[bool] = Field(default=False)

    # Shortage/Damage Details
    deducted_amount: Optional[Decimal] = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(10, 2), nullable=True)
    )
    deducted_details: Optional[str] = Field(default=None, max_length=500)
 
    instructions: Optional[str] = Field(default=None, max_length=1000)
    
    cancellation_reason: Optional[str] = Field(default=None, max_length=500)
    is_advance_payment_done: Optional[bool] = Field(default=False)
    is_advance_given: Optional[bool] = Field(default=False)
    is_balance_payment_approve: Optional[bool] = Field(default=False)
    pod_sent_to_customer: Optional[bool] = Field(default=False)
    
    # Relationships
    branch: "Branch" = Relationship()
    customer: "Customer" = Relationship()
    vehicle_type: "VehicleType" = Relationship()
    addresses: list["TripAddress"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    status_history: list["TripStatusHistory"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "TripStatusHistory.created_at"}
    )
    assigned_vendor: Optional["TripVendor"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    trip_documents: Optional["TripDocument"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"}
    )
    @property
    def vehicle_unloaded_date(self) -> Optional[date]:
        """Get the date when vehicle was unloaded from status history"""
        if not self.status_history:
            return None
        
        for history in reversed(self.status_history):
            if history.current_status == TripStatusEnum.VEHICLE_UNLOADED:
                return history.created_at.date()
        return None
    
    @property
    def pod_submission_last_date(self) -> Optional[date]:
        """Calculate POD submission last date (18 days from unloading date)"""
        unloaded_date = self.vehicle_unloaded_date
        if not unloaded_date:
            return None
        
        # Next day after unloading + 18 days
        return unloaded_date + timedelta(days=19)  # +1 for next day, +18 for grace period
    
    @property
    def pod_submitted_date(self) -> Optional[date]:
        """Get the date when POD was submitted from status history"""
        if not self.status_history:
            return None
        
        for history in reversed(self.status_history):
            if history.current_status == TripStatusEnum.POD_SUBMITTED:
                return history.created_at.date()
        return None
    
    @property
    def payment_type(self) -> Optional[str]:
        if self.is_advance_payment_done and self.is_advance_given:
            return "balance"
        elif not self.is_advance_payment_done:
            return "advance"
        else:
            return None

    
    @property
    def pod_overdue_days(self) -> int:
        """Calculate overdue days if POD submitted after last date"""
        submission_date = self.pod_submitted_date
        last_date = self.pod_submission_last_date

        print(f"Submission Date: {submission_date}")
        print(f"Last Date: {last_date}")


        if not submission_date and not last_date:
            return 0

        if not submission_date and last_date:
            today = date.today()
            if today > last_date:
                return (today - last_date).days
            else:
                return 0

        elif submission_date > last_date:
            return (submission_date - last_date).days
        else:
            return 0
    
    @property
    def pod_penalty_amount(self) -> Decimal:
        """Calculate penalty amount (₹100 per overdue day)"""
        overdue_days = self.pod_overdue_days

        print(f"Overdue days: {overdue_days}")
        return Decimal(overdue_days * 100)

class TripVendor(BaseTable, table=True):
    __tablename__ = "marketline_trip_vendors"
    
    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)
    branch_id: UUID = Field(foreign_key="marketline_branches.id", nullable=False)
    vendor_id: UUID = Field(foreign_key="marketline_vendors.id", nullable=False)

    # Vehicle details
    vehicle_type_id: UUID = Field(foreign_key="marketline_vehicle_types.id", nullable=False)
    tons: int = Field(nullable=False)
    vehicle_no: str = Field(nullable=False, max_length=50)
    insurance_expiry_date: date = Field(nullable=False)
    rc_copy: Optional[str] = Field(default=None, max_length=255)
    insurance_copy: Optional[str] = Field(default=None, max_length=255)

    # Fleet Details
    trip_rate: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    advance: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    other_charges: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(10, 2), nullable=False)
    )

    other_unloading_charges: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(10, 2), nullable=False)
    )

    # Relationships
    trip: "Trip" = Relationship(back_populates="assigned_vendor")
    branch: "Branch" = Relationship()
    vendor: "Vendor" = Relationship()
    vehicle_type: "VehicleType" = Relationship()
    drivers: list["TripDriver"] = Relationship(
        back_populates="trip_vendor",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "desc(TripDriver.created_at)"
        }
    )

    @property
    def balance(self) -> Optional[date]:
        balance_amount = 0
        if self.trip_rate:
            balance_amount += self.trip_rate
        if self.other_charges:
            balance_amount += self.other_charges
        if self.advance:
            balance_amount -= self.advance
        return balance_amount



class TripDriver(BaseTable, table=True):
    __tablename__ = "marketline_trip_drivers"

    trip_vendor_id: UUID = Field(foreign_key="marketline_trip_vendors.id", nullable=False)

    driver_name: str = Field(nullable=False, max_length=255)
    driver_mobile_no: str = Field(nullable=False, max_length=20)
    driver_licence_no: str = Field(nullable=False, max_length=50)
    driver_licence_expiry: date = Field(nullable=False)

    # Relationship
    trip_vendor: "TripVendor" = Relationship(back_populates="drivers")


class TripDocument(BaseTable, table=True):
    __tablename__ = "marketline_trip_documents"
    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)

    # Loading Vehicle Documents
    eway_bill: str = Field(max_length=255)
    invoice_copy: str = Field(max_length=255)
    vehicle_image: str = Field(max_length=255)
    lr_copy: str = Field(max_length=255)

    # Unloading Vehicle Documents
    pod_submit: str = Field(default=False,max_length=255)
    comments: Optional[str] = Field(default=None, max_length=500)

    # Relationships
    trip: "Trip" = Relationship(back_populates="trip_documents")
