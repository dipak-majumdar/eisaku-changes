from uuid import UUID
from pydantic import BaseModel


class Base(BaseModel):
    model_name: str
    action_name: str
    description: str | None = None


class PermissionRead(Base):
    id: UUID

    class Config:
        from_attributes = True


class PermissionCreate(Base):
    pass


class PermissionUpdate(Base):
    model_name: str | None = None
    action_name: str | None = None
    description: str | None = None


class PermissionReadWithRequired(Base):
    required: bool   # 👈 comes from RolePermission

    class Config:
        from_attributes = True


class PermissionList(BaseModel):
    
    results: list[PermissionRead] = []
