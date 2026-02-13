# api/routes/trip.py

from uuid import UUID
from fastapi import APIRouter, Depends, Request, status, Query
from typing import Optional, List
from datetime import date

from core.security import permission_required
from api.deps import get_trip_service
from models.enums import TimePeriodEnum
from models.trip import TripStatusEnum, GoodsTypeEnum
from schemas.trip import (
    # TripList as ListSchema,
    TripRead as ReadSchema,
    TripCreate as CreateSchema,
    TripUpdate as UpdateSchema,
    TripStatusUpdate,
    TripMinimalList,
)
from services.trip import Service as TripService


router = APIRouter()

CREATE_PERMISSION = 'trip.can_create'
CHANGE_PERMISSION = 'trip.can_change'
VIEW_PERMISSION = 'trip.can_view'
DELETE_PERMISSION = 'trip.can_delete'
ASSIGN_VENDOR_PERMISSION = 'trip.can_assign_vendor'
APPROVE_PERMISSION = 'trip.can_approve'
REJECT_PERMISSION = 'trip.can_reject'
LOAD_VEHICLE_PERMISSION = 'trip.can_load_vehicle'
UNLOAD_VEHICLE_PERMISSION = 'trip.can_unload_vehicle'
POD_SUBMIT_PERMISSION = 'trip.can_pod_submit'



# GET GOODS TYPES
@router.get("/goods-types/", response_model=List[str])
@permission_required()
async def list_goods_types(request: Request):
    return [e.value for e in GoodsTypeEnum]

# # LIST
# @router.get("/", response_model=ListSchema)
# @permission_required(VIEW_PERMISSION)
# async def list_trips(
#     request: Request,
#     page: int = 1,
#     size: int = 10,
#     search: Optional[str] = None,
#     customer_id: Optional[UUID] = None,
#     branch_id: Optional[UUID] = None,
#     time_period: TimePeriodEnum | None = None, 
#     start_date: Optional[date] = Query(
#         None,
#         description="Start date for filtering (format: YYYY-MM-DD, example: 2025-01-01)",
#         example=""
#     ),
#     end_date: Optional[date] = Query(
#         None,
#         description="End date for filtering (format: YYYY-MM-DD, example: 2025-12-31)",
#         example=""
#     ), 
#     trip_status: Optional[TripStatusEnum] = None,
#     service: TripService = Depends(get_trip_service),
# ):
#     return await service.list(
#         request, page=page, size=size, search=search,
#         customer_id=customer_id, branch_id=branch_id, time_period=time_period, start_date=start_date, end_date=end_date, trip_status=trip_status
#     )


# MINIMAL LIST
@router.get("/", response_model=TripMinimalList)
@permission_required(VIEW_PERMISSION)
async def list_trips_minimal(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    branch_id: Optional[UUID] = None,
    time_period: TimePeriodEnum | None = None, 
    start_date: Optional[date] = Query(
        None,
        description="Start date for filtering (format: YYYY-MM-DD, example: 2025-01-01)",
        example=""
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for filtering (format: YYYY-MM-DD, example: 2025-12-31)",
        example=""
    ), 
    trip_status: Optional[TripStatusEnum] = None,
    service: TripService = Depends(get_trip_service),
):
    """Fast trip listing with minimal data (optimized for performance)"""
    return await service.list_minimal(
        request, page=page, size=size, search=search,
        customer_id=customer_id, branch_id=branch_id, time_period=time_period, start_date=start_date, end_date=end_date, trip_status=trip_status
    )


# READ
@router.get("/{id}/", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_trip(
    request: Request,
    id: UUID,
    service: TripService = Depends(get_trip_service),
):
    return await service.read(request, id)


# ✅ CREATE (Form Data)
@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create_trip(
    request: Request,
    item: CreateSchema,
    service: TripService = Depends(get_trip_service),
):
    """
    Create a new trip by sending a raw JSON payload in the request body.
    """
    return await service.create(request, item)


# ✅ UPDATE (Form Data)
@router.put("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_trip(
    request: Request,
    id: UUID,
    item: UpdateSchema,
    service: TripService = Depends(get_trip_service),
):
    """
    Update a trip by sending a raw JSON payload in the request body.
    """
    return await service.update(request, id, item)


# UPDATE TRIP STATUS
@router.patch("/{id}/status/", response_model=ReadSchema)
@permission_required(APPROVE_PERMISSION,REJECT_PERMISSION)
async def update_trip_status(
    request: Request,
    id: UUID,
    item: TripStatusUpdate,
    service: TripService = Depends(get_trip_service),
):
    """
    Update the status of a trip and create trip status history.
    """
    return await service.update_status(request, id, item)


# DELETE
@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_trip(
    request: Request,
    id: UUID,
    service: TripService = Depends(get_trip_service),
):
    return await service.delete(request=request, id=id)

