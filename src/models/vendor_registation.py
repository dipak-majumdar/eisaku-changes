from typing import TYPE_CHECKING, List, Optional
from uuid import UUID
import enum
from sqlmodel import Field, Relationship
from db.base import BaseTable

if TYPE_CHECKING:
    from .region import Region
    from .vehicle_type import VehicleType
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .vendor import Vendor

class VendorRegistrationStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class VendorVehicleType(BaseTable, table=True):
    __tablename__ = "marketline_vendor_vehicle_type"
    vendor_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vendor_registrations.id", primary_key=True)
    vehicle_type_id: Optional[UUID] = Field(default=None, foreign_key="marketline_vehicle_types.id", primary_key=True)

class VendorRegistration(BaseTable, table=True):
    __tablename__ = "marketline_vendor_registrations"

    transporter_firm_name: str = Field(nullable=False, max_length=255)
    owner_name: str = Field(nullable=False, max_length=255)
    contact_number: str = Field(nullable=False, max_length=20)
    gst_number: Optional[str] = Field(default=None, max_length=50,unique=True)
    gst_document: Optional[str] = Field(default=None, max_length=255)  # File path or URL
    pan_card_number: Optional[str] = Field(default=None, max_length=50,unique=True)
    pan_card_document: Optional[str] = Field(default=None, max_length=255)  # File path or URL

    country_id: UUID = Field(foreign_key="marketline_countries.id", nullable=False)
    state_id: UUID = Field(foreign_key="marketline_states.id", nullable=False)
    district_id: UUID = Field(foreign_key="marketline_districts.id", nullable=False)
    city_id: UUID = Field(foreign_key="marketline_cities.id", nullable=False)
    pin_code: str = Field(nullable=False, max_length=20)
    location: str = Field(nullable=False, max_length=255)
    region_id: UUID = Field(foreign_key="marketline_regions.id", nullable=False)
    total_vehicle_owned: int = Field(nullable=False)

    route: str = Field(nullable=False, max_length=20)  # Expected values: 'All India' or 'Specific Route'

    visiting_card: Optional[str] = Field(default=None, max_length=255)  # File path or URL
    status: VendorRegistrationStatusEnum = Field(default=VendorRegistrationStatusEnum.PENDING, nullable=False)

    # Relationships
    country: "Country" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    state: "State" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    district: "District" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    city: "City" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    region: "Region" = Relationship(sa_relationship_kwargs={"lazy": "joined"})

    vehicle_types: List["VehicleType"] = Relationship(
        link_model=VendorVehicleType,
        back_populates="vendors"
    
    )

   