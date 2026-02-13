# routes/target.py

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Request, Query
from uuid import UUID

from core.security import permission_required
from api.deps import get_target_service as get_service
from models.target import TargetStatusEnum
from models.enums import TimePeriodEnum
from services import TargetService as Service
from schemas import (
    TargetDetail as ReadSchema, 
    TargetList as ListSchema, 
    TargetCreate as CreateSchema, 
    TargetUpdate as UpdateSchema
)
from schemas.target import TargetStatusUpdate

CREATE_PERMISSION = 'target.can_create'
CHANGE_PERMISSION = 'target.can_change'
ARROVE_PERMISSION = 'target.can_approve'
REJECT_PERMISSION = 'target.can_reject'
VIEW_PERMISSION = 'target.can_view'
DELETE_PERMISSION = 'target.can_delete'

router = APIRouter()


@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list_targets(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    branch_id: UUID | None = Query(None, description="Filter by branch"),
    status: TargetStatusEnum | None = Query(None, description="Filter by status"),
    time_period: TimePeriodEnum | None = None, 
    start_date: Optional[date] = Query(None, description="Filter start date"),
    end_date: Optional[date] = Query(None, description="Filter end date"), 
    service: Service = Depends(get_service),
):
    """
    List all targets with filtering options
    
    **Branch Manager Behavior**:
    - Branch Managers can only see targets for their own branch
    - The branch_id filter parameter is ignored for Branch Managers
    
    Filters:
    - search: Search by branch name
    - branch_id: Filter by specific branch (admins only)
    - status: Filter by target status
    - time_period: Filter by time period
    """
    return await service.list(request, page, size, search, branch_id, status, time_period, start_date, end_date)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create_target(
    request: Request,
    item: CreateSchema, 
    service: Service = Depends(get_service)
):
    """
    Create a new target
    
    Validates:
    - Branch exists
    - No overlapping targets for same branch
    - end_date is after start_date
    """
    return await service.create(request, item)


@router.get("/{item_id}/", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_target(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    """Get target details by ID"""
    return await service.read(request, item_id)


@router.put("/{item_id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_target(
    request: Request,
    item_id: UUID, 
    item: UpdateSchema, 
    service: Service = Depends(get_service)
):
    """
    Update target (only allowed for Pending targets)
    """
    return await service.update(request, item_id, item)


@router.patch("/{item_id}/status/", response_model=ReadSchema)
@permission_required(ARROVE_PERMISSION, REJECT_PERMISSION)
async def update_target_status(
    request: Request,
    item_id: UUID,
    data: TargetStatusUpdate,
    service: Service = Depends(get_service)
):
    """
    Update target status
    
    Status Transitions:
    - Pending → Approved/Rejected
    - Approved → Closed
    - Rejected → (Cannot change)
    - Closed → (Cannot change)
    
    Rejection reason is required when status is Rejected
    """
    return await service.update_status(request, item_id, data)


@router.delete("/{item_id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_target(
    request: Request,
    item_id: UUID,
    service: Service = Depends(get_service)
):
    """Delete target (only Pending or Rejected targets can be deleted)"""
    return await service.delete(request, item_id)