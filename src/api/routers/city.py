from fastapi import APIRouter, Depends, status, Request
from uuid import UUID

from core.security import permission_required
from api.deps import get_city_service as get_service

from services import CityService as Service
from schemas import (
    CityRead as ReadSchema, 
    CityList as ListSchema, 
    CityCreate as CreateSchema, 
    CityUpdate as UpdateSchema
)

CREATE_PERMISSION = 'city.can_create'
CHANGE_PERMISSION = 'city.can_change'
VIEW_PERMISSION = 'city.can_view'
DELETE_PERMISSION = 'city.can_delete'


router = APIRouter()


@router.get("/", response_model=ListSchema)
@permission_required()
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    district_id: UUID | None = None,
    service: Service = Depends(get_service),
):
    return await service.list(request, page=page, size=size, search=search, district_id=district_id)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create(
    request: Request,
    item: CreateSchema, 
    service: Service = Depends(get_service)
):
    return await service.create(request, item)


@router.get("/{item_id}", response_model=ReadSchema)
@permission_required()
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
