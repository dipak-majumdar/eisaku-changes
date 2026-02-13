from fastapi import APIRouter, Depends, status, Request
from uuid import UUID

from core.security import permission_required
from api.deps import get_role_service as get_service
from schemas.role import ActiveRoleList
from services import RoleService as Service
from schemas import (
    RoleRead as ReadSchema, 
    RoleList as ListSchema, 
    RoleCreate as CreateSchema, 
    RoleUpdate as UpdateSchema,
    RolePermissionRead
)

CREATE_PERMISSION = 'role.can_create'
CHANGE_PERMISSION = 'role.can_change'
VIEW_PERMISSION = 'role.can_view'
DELETE_PERMISSION = 'role.can_delete'


router = APIRouter()

@router.get("/active-roles/", response_model=ActiveRoleList)
@permission_required()
async def active_role_list(
    request: Request,
    search: str | None = None,
    service: Service = Depends(get_service),
):
    return await service.active_list(request, search=search)

@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    service: Service = Depends(get_service),
):
    return await service.list(request, page=page, size=size, search=search)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create(
    request: Request,
    item: CreateSchema, 
    service: Service = Depends(get_service)
):
    return await service.create(request, item)


@router.get("/{item_id}", response_model=RolePermissionRead)
@permission_required(VIEW_PERMISSION)
async def read(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    return await service.read(request, item_id)


@router.put("/{item_id}", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update(
    request: Request,
    item_id: UUID, 
    item: UpdateSchema, 
    service: Service = Depends(get_service)
):
    return await service.update(request, item_id, item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete(
    request: Request,
    item_id: UUID,
    service: Service = Depends(get_service)
):
    return await service.delete(request, item_id)


@router.patch("/{item_id}/status")
@permission_required(CHANGE_PERMISSION)
async def toggle_active(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    return await service.toggle_active(request, item_id)


@router.get("/branch-context/roles", response_model=ActiveRoleList)
@permission_required()
async def branch_roles(
    request: Request,
    branch_id: UUID | None = None,
    service: Service = Depends(get_service),
):
    """
    Get roles for branch employee creation.
    If branch_id provided: returns Field Executive, Supervisor, Supplier Lead
    If no branch_id: returns all active roles
    """
    return await service.branch_roles_list(request, branch_id=branch_id)
