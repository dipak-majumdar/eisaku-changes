from uuid import UUID
from sqlmodel import Field, Relationship
from typing import TYPE_CHECKING

from db.base import BaseTable


if TYPE_CHECKING:
    from .role import Role
    from .permission import Permission


class RolePermission(BaseTable, table=True):
    __tablename__ = "marketline_role_permissions"

    role_id: UUID = Field(foreign_key="marketline_roles.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="marketline_permissions.id", primary_key=True)
    required: bool = Field(default=False, nullable=False)

    # Relationships back to Role and Permission
    role: "Role" = Relationship(back_populates="role_permissions", sa_relationship_kwargs={"lazy": "joined"})
    permission: "Permission" = Relationship(back_populates="role_permissions", sa_relationship_kwargs={"lazy": "joined"})