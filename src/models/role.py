from uuid import UUID
from sqlmodel import Field, Relationship
from typing import TYPE_CHECKING

from db.base import BaseTable


from .role_permission import RolePermission
if TYPE_CHECKING:
    from .permission import Permission
    from .user import User  # only for type hint


class Role(BaseTable, table=True):
    __tablename__ = "marketline_roles"

    name: str = Field(index=True, unique=True, nullable=False, max_length=255)
    description: str | None = Field(default=None, max_length=255)

    # ✅ Reverse relation
    role_permissions: list["RolePermission"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={
            "lazy": "joined",
            "cascade": "all, delete-orphan"
        }
    )
    users: list["User"] = Relationship(
        back_populates="role",
        sa_relationship_kwargs={"lazy": "joined"}
    )
    permissions: list["Permission"] = Relationship(
        back_populates="roles", 
        link_model=RolePermission,
        sa_relationship_kwargs={"lazy": "joined"}
    )
