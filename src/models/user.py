from uuid import UUID
from sqlmodel import Field, Relationship
from typing import TYPE_CHECKING
from db.base import BaseTable


if TYPE_CHECKING:
    from .role import Role  # only for type hint
    from .employee import Employee
    from .customer import Customer
    from .vendor import Vendor


class User(BaseTable, table=True):
    __tablename__ = "marketline_users"

    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    username: str = Field(index=True, unique=True, nullable=False, max_length=255)
    email: str = Field(index=True, unique=True, nullable=False, max_length=255)
    mobile: str = Field(index=True, unique=True, nullable=False, max_length=20)
    hashed_password: str = Field(nullable=False, max_length=255)
    
    # ✅ Foreign key to user's role
    role_id: UUID = Field(foreign_key="marketline_roles.id", nullable=False)

    # ✅ Relationship
    role: "Role" = Relationship(back_populates="users", sa_relationship_kwargs={"lazy": "joined"})

    # ✅ Reverse Relationships (One-to-One)
    employee: "Employee" = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})
    customer: "Customer" = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})
    vendor: "Vendor" = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})

    @property
    def name(self) -> str:
        """Return full name combining first_name and last_name."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.first_name