from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Request,Query
from uuid import UUID

from core.security import permission_required
from api.deps import get_region_service as get_service
from models.enums import TimePeriodEnum
from services import RegionService as Service
from schemas import (
    RegionRead as ReadSchema, 
    RegionList as ListSchema, 
    RegionCreate as CreateSchema, 
    RegionUpdate as UpdateSchema,
)

CREATE_PERMISSION = 'region.can_create'
CHANGE_PERMISSION = 'region.can_change'
VIEW_PERMISSION = 'region.can_view'
DELETE_PERMISSION = 'region.can_delete'


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
        description="Start date for filtering (format: YYYY-MM-DD)",
        example="2025-01-01"
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for filtering (format: YYYY-MM-DD)",
        example="2025-12-31"
    ),
    has_manager: Optional[bool] = Query(
        None,
        description="Filter regions by whether they have an assigned Regional Manager (True/False)",
        example=True
    ),
    service: Service = Depends(get_service),
):
    """
    List all regions with optional filtering.
    
    **Query Parameters:**
    - page: Page number (default: 1)
    - size: Items per page (default: 10)
    - search: Search by region name
    - time_period: Filter by time period
    - start_date: Start date for filtering
    - end_date: End date for filtering
    - has_manager: Filter by Regional Manager presence
      - `true`: Only regions WITH a Regional Manager
      - `false`: Only regions WITHOUT a Regional Manager
      - `null` (omit parameter): All regions
    """
    return await service.list(
        request,
        page=page,
        size=size,
        search=search,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date,
        has_manager=has_manager
    )


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


@router.patch("/{item_id}/status")
@permission_required(CHANGE_PERMISSION)
async def toggle_active(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    return await service.toggle_active(request, item_id)
