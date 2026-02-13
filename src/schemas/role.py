from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from .permission import PermissionRead, PermissionReadWithRequired


class Base(BaseModel):
    name: str
    description: str | None = None

class PermissionAssign(BaseModel):
    id: UUID
    required: bool = False

class RoleCreate(Base):
    permissions: list[PermissionAssign] | None = []


class RoleUpdate(Base):
    name: str | None = None
    description: str | None = None
    permissions: list[PermissionAssign] | None = []


class RoleRead(Base):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None

    class Config:
        from_attributes = True 


class RolePermissionRead(RoleRead):
    permissions: list[PermissionReadWithRequired] = []


class RoleList(BaseModel):
    total: int
    next: str | None = None
    previous: str | None = None
    results: list[RoleRead] = []


class ActiveRoleList(BaseModel):
    results: list[RoleRead] = []

