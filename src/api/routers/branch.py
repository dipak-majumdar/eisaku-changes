from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Request,Query
from uuid import UUID
from core.security import permission_required
from api.deps import get_branch_service as get_service
from models.enums import TimePeriodEnum
from schemas.branch import BranchManagerUpdate
from services import BranchService as Service
from schemas import (
    BranchRead as ReadSchema, 
    BranchList as ListSchema, 
    BranchCreate as CreateSchema, 
    BranchUpdate as UpdateSchema
)

CHANGE_MANAGER_PERMISSION = 'branch.can_change_manager'  
CREATE_PERMISSION = 'branch.can_create'
CHANGE_PERMISSION = 'branch.can_change'
VIEW_PERMISSION = 'branch.can_view'
DELETE_PERMISSION = 'branch.can_delete'

router = APIRouter()

@router.get("/", response_model=ListSchema)
@permission_required()
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    country_id: UUID | None = None,
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
    has_manager: Optional[bool] = Query(
        None,
        description="Filter branches by whether they have an assigned manager (True/False)",
        example=True
    ),
    service: Service = Depends(get_service),
):
    return await service.list(request, page=page, size=size, search=search, country_id=country_id, time_period=time_period, start_date=start_date, end_date=end_date, has_manager=has_manager)

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




@router.patch("/{branch_id}/manager", response_model=ReadSchema)
@permission_required(CHANGE_MANAGER_PERMISSION)
async def change_branch_manager(
    request: Request,
    branch_id: UUID,
    data: BranchManagerUpdate,
    service: Service = Depends(get_service)
):
    """
    Change the branch manager and update all employees.
    
    - Validates new manager is active employee with "Branch Manager" role
    - Updates all employees in the branch to report to new manager
    - Sets new manager's manager_id to None
    """
    return await service.change_branch_manager(
        request, 
        branch_id, 
        data.manager_employee_id
    )