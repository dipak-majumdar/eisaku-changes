from typing import TYPE_CHECKING, List
from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship

from db.base import BaseTable


if TYPE_CHECKING:
    from .state import State
    from .city import City

class District(BaseTable, table=True):
    __tablename__ = "marketline_districts"

    name: str = Field(
        sa_column_kwargs={"unique": True, "nullable": False},
        max_length=255
       
    )
    state_id: UUID = Field(foreign_key="marketline_states.id", nullable=False)
    
    state: "State" = Relationship(
        back_populates="districts",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    cities: List["City"] = Relationship(
        back_populates="district",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
