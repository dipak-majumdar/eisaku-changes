from typing import List, TYPE_CHECKING
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship


from .role_permission import RolePermission
if TYPE_CHECKING:
    from .role import Role


class Permission(SQLModel, table=True):
    __tablename__ = 'marketline_permissions'

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    model_name: str = Field(nullable=False, max_length=255)
    action_name: str = Field(nullable=False, max_length=255)
    description: str | None = Field(default=None, max_length=255)

    # Relationship to roles via RolePermission
    role_permissions: list["RolePermission"] = Relationship(
        back_populates="permission"
    )
    roles: list["Role"] = Relationship(
        back_populates="permissions", 
        link_model=RolePermission
    )