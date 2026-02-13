from fastapi import APIRouter, Depends, status, Request
from uuid import UUID

from core.security import permission_required
from api.deps import get_permission_service as get_service
from services import PermissionService as Service
from schemas import (
    PermissionRead as ReadSchema, 
    PermissionList as ListSchema, 
    PermissionCreate as CreateSchema, 
    PermissionUpdate as UpdateSchema,
)

CREATE_PERMISSION = 'permission.can_create'
CHANGE_PERMISSION = 'permission.can_change'
VIEW_PERMISSION = 'permission.can_view'
DELETE_PERMISSION = 'permission.can_delete'


router = APIRouter()



@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list(
    request: Request,
    search: str | None = None, 
    service: Service = Depends(get_service),
):
    return await service.list(request, search=search)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create(
    request: Request,
    item: CreateSchema, 
    service: Service = Depends(get_service)
):
    return await service.create(request, item)


@router.get("/{item_id}", response_model=ReadSchema)
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

