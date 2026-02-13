from uuid import UUID
from typing import TYPE_CHECKING, List
from sqlmodel import Field, SQLModel, Relationship
from db.base import BaseTable
from .vendor_registation import VendorVehicleType,VendorRegistration
from .vendor import VendorVehicleLink
if TYPE_CHECKING:
    from .vendor import Vendor
 # for type hints only



class VehicleType(BaseTable, table=True):
    __tablename__ = "marketline_vehicle_types"

    name: str = Field(nullable=False, unique=True, max_length=255)

    vendors: List["VendorRegistration"] = Relationship(
        back_populates="vehicle_types",
        link_model=VendorVehicleType,
        sa_relationship_kwargs={"lazy": "joined"}
    )

    vendors_new: List["Vendor"] = Relationship(link_model=VendorVehicleLink, back_populates="vehicle_types")
