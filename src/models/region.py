from sqlmodel import Field
from db.base import BaseTable


class Region(BaseTable, table=True):
    __tablename__ = "marketline_regions"

    name: str = Field(index=True, unique=True, nullable=False, max_length=255)
