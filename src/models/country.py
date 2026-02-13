from uuid import UUID, uuid4
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import SQLModel, Field, Relationship

from db.base import BaseTable


if TYPE_CHECKING:
    from .state import State 

class Country(BaseTable, table=True):
    __tablename__ = "marketline_countries"

    name: str = Field(
        sa_column_kwargs={"unique": True, "nullable": False},
        max_length=255,
       
    )

    states: List["State"] = Relationship(
        back_populates="country",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
