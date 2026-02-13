from typing import TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship
import json
import os
from db.base import BaseTable
from utils.get_region import get_region_data

if TYPE_CHECKING:
    from .employee import Employee
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .vendor import Vendor
 
# --- Load Region Data ---
class Branch(BaseTable, table=True):
    __tablename__ = 'marketline_branches'

    name: str = Field(unique=True, nullable=False, max_length=255)
    country_id: UUID = Field(foreign_key="marketline_countries.id", nullable=False)
    state_id: UUID = Field(foreign_key="marketline_states.id", nullable=False)
    district_id: UUID = Field(foreign_key="marketline_districts.id", nullable=False)
    city_id: UUID = Field(foreign_key="marketline_cities.id", nullable=False)
    pin_code: str = Field(nullable=False, max_length=20)
    location: str = Field(nullable=False, max_length=255)
    code: str = Field(unique=True, nullable=False, max_length=50)
    email: str = Field(nullable=True, max_length=255)
    mobile: str = Field(nullable=True, max_length=20)

    country: "Country" = Relationship()
    state: "State" = Relationship()
    district: "District" = Relationship()
    city: "City" = Relationship()
    employees: list["Employee"] = Relationship(back_populates="branch")
    vendors: list["Vendor"] = Relationship(back_populates="branch")

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
    def branch_region(self) -> dict:
        """Finds the region for the branch based on its state name."""
        region_map = get_region_data()


        if not self.state or not self.state.name:
            return  None

        region_name = region_map.get(self.state.name.lower())

        return  region_name
        
