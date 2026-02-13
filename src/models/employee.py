

from typing import TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship
from db.base import BaseTable

if TYPE_CHECKING:
    from .user import User
    from .branch import Branch
    from .country import Country
    from .state import State
    from .district import District
    from .city import City
    from .region import Region


class Employee(BaseTable, table=True):
    __tablename__ = 'marketline_employees'

    user_id: UUID = Field(foreign_key="marketline_users.id", nullable=False)
    branch_id: UUID = Field(foreign_key="marketline_branches.id",nullable=True)
    manager_id: UUID = Field(foreign_key="marketline_employees.id",nullable=True)
    country_id: UUID = Field(foreign_key="marketline_countries.id", nullable=False)
    state_id: UUID = Field(foreign_key="marketline_states.id", nullable=False)
    district_id: UUID = Field(foreign_key="marketline_districts.id", nullable=False)
    city_id: UUID = Field(foreign_key="marketline_cities.id", nullable=False)
    region_id: UUID = Field(foreign_key="marketline_regions.id", nullable=True)
    pin_code: str = Field(nullable=False, max_length=20)
    location: str = Field(nullable=False, max_length=255)
    employee_code: str = Field(unique=True, nullable=False, index=True, max_length=10)
    employee_pic: str = Field(max_length=255)

    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    branch: "Branch" = Relationship(back_populates="employees", sa_relationship_kwargs={"lazy": "joined"})
    manager: "Employee" = Relationship(back_populates="reports", sa_relationship_kwargs={"remote_side": "Employee.id", "lazy": "joined"})
    reports: list["Employee"] = Relationship(back_populates="manager", sa_relationship_kwargs={"lazy": "joined"})
    country: "Country" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    state: "State" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    district: "District" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    city: "City" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    region: "Region" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    
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
            "region": getattr(self.region, "name", None)
        }
    