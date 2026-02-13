from typing import TYPE_CHECKING, List
from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship
from db.base import BaseTable


if TYPE_CHECKING:
    from .country import Country
    from .district import District

class State(BaseTable, table=True):
    __tablename__ = "marketline_states"

  
    name: str = Field(
        sa_column_kwargs={"unique": True, "nullable": False},
        max_length=255
    )
    country_id: UUID = Field(foreign_key="marketline_countries.id", nullable=False)
   
   
    country: "Country" = Relationship(
        back_populates="states",
        sa_relationship_kwargs={"lazy": "joined"}
    )
    districts: List["District"] = Relationship(
        back_populates="state",
        sa_relationship_kwargs={"lazy": "joined"}
    )
