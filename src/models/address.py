
from uuid import UUID
from sqlmodel import Field, Relationship
from db.base import BaseTable

from .country import Country
from .state import State
from .district import District
from .city import City

 

class Address(BaseTable, table=True):
    __tablename__ = 'marketline_addresses'

    location: str = Field(nullable=False, max_length=255)
    pin_code: str = Field(nullable=False, max_length=6)
    country_id: UUID = Field(foreign_key="marketline_countries.id")
    state_id: UUID = Field(foreign_key="marketline_states.id")
    district_id: UUID = Field(foreign_key="marketline_districts.id")
    city_id: UUID = Field(foreign_key="marketline_cities.id")

    # Relationship
    country: Country = Relationship()
    state: State = Relationship()
    district: District = Relationship()
    city: City = Relationship()

