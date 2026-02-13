from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship

from db.base import BaseTable


if TYPE_CHECKING:
    from .district import District

class City(BaseTable, table=True):
    __tablename__ = "marketline_cities"

    name: str = Field(
        sa_column_kwargs={"unique": True, "nullable": False},
        max_length=255
    )
    district_id: UUID = Field(foreign_key="marketline_districts.id", nullable=False)
    

    district: "District" = Relationship(
        back_populates="cities",
        sa_relationship_kwargs={"lazy": "selectin"}
    )