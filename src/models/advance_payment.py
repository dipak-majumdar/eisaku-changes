from typing import TYPE_CHECKING
from uuid import UUID
from datetime import date
from decimal import Decimal
from sqlmodel import Field, Relationship, Column
from sqlalchemy import Numeric
from db.base import BaseTable

if TYPE_CHECKING:
    from .customer import Customer
    from .vendor import Vendor
    from .trip import Trip


class AdvancePayment(BaseTable, table=True):
    __tablename__ = "marketline_advance_payments"

    customer_id: UUID = Field(foreign_key="marketline_customers.id", nullable=True)
    vendor_id: UUID | None = Field(default=None, foreign_key="marketline_vendors.id", nullable=True)
    trip_id: UUID = Field(foreign_key="marketline_trips.id", nullable=False)
    payment_date: date | None = Field(default=None)
    utr_no: str | None = Field(default=None, max_length=100, index=True)
    
    amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    payment_type: str = Field(default=None, max_length=200, index=True)
    # payment_status: str = Field(default=None, max_length=100, index=True)
    is_paid_amount: bool = Field(default=True)
    is_deduct_amount: bool = Field(default=False)
    is_payment_due: bool = Field(default=False)
    
    # Relationships
    customer: "Customer" = Relationship()
    vendor: "Vendor" = Relationship()
    trip: "Trip" = Relationship()
