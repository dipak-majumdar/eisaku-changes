from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Request,Query
from uuid import UUID

from core.security import permission_required
from api.deps import get_vehicle_type_service as get_service
from models.enums import TimePeriodEnum
from services import VehicleTypeService as Service
from schemas import (
    VehicleTypeRead as ReadSchema, 
    VehicleTypeList as ListSchema, 
    VehicleTypeCreate as CreateSchema, 
    VehicleTypeUpdate as UpdateSchema
)

CREATE_PERMISSION = 'vehicle_type.can_create'
CHANGE_PERMISSION = 'vehicle_type.can_change'
VIEW_PERMISSION = 'vehicle_type.can_view'
DELETE_PERMISSION = 'vehicle_type.can_delete'


router = APIRouter()


@router.get("/", response_model=ListSchema)
@permission_required()
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    time_period: TimePeriodEnum | None = None, 
    start_date: Optional[date] = Query(
        None,
        description="Start date for filtering (format: YYYY-MM-DD, example: 2025-01-01)",
        example="2025-01-01"
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for filtering (format: YYYY-MM-DD, example: 2025-12-31)",
        example="2025-12-31"
    ), 
    service: Service = Depends(get_service),
):
    return await service.list(request, page=page, size=size, search=search, time_period=time_period, start_date=start_date, end_date=end_date)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)

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


@router.patch("/{item_id}/status")
@permission_required(CHANGE_PERMISSION)
async def toggle_active(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    return await service.toggle_active(request, item_id)
