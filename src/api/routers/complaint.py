from uuid import UUID
from fastapi import APIRouter, Depends, Request, status, Query
from datetime import date
from typing import Optional

from core.security import permission_required
from api.deps import get_complaint_service
from schemas.complaint import (
    ComplaintList as ListSchema,
    ComplaintListDashboard,
    ComplaintRead as ReadSchema,
    ComplaintCreate as CreateSchema,
    ComplaintUpdate as UpdateSchema,
    ComplaintStatusUpdate as StatusUpdateSchema,
    ComplaintDetailRead,
)
from services import ComplaintService
from models.complaint import UserTypeEnum, ComplaintStatusEnum, SubjectTypeEnum
from models.enums import TimePeriodEnum


router = APIRouter()

CREATE_PERMISSION = 'complain.can_create'
CHANGE_PERMISSION = 'complain.can_change'
VIEW_PERMISSION = 'complain.can_view'
IN_PROGRESS_PERMISSION = 'complain.can_inprogress'
CLOSE_PERMISSION = 'complain.can_close'
DELETE_PERMISSION = 'complain.can_delete'

@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list_complaints(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = None,
    user_type: Optional[UserTypeEnum] = Query(None, description="Filter by user type (Customer/Vendor)"),
    status: Optional[ComplaintStatusEnum] = Query(None, description="Filter by status"),
    subject_type: Optional[SubjectTypeEnum] = Query(None, description="Filter by subject type (Block/Other)"),
    vendor_id: Optional[UUID] = Query(None, description="Filter by vendor UUID"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer UUID"),
    time_period: Optional[TimePeriodEnum] = Query(None, description="Filter by time period"),
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
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    List complaints with optional filters
    """
    return await service.list(
        request, 
        page=page, 
        size=size, 
        search=search,
        user_type=user_type,
        status=status,
        subject_type=subject_type,
        vendor_id=vendor_id,
        customer_id=customer_id,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date
    )


# READ ENDPOINT
@router.get("/{id}/", response_model=ComplaintDetailRead)
@permission_required(VIEW_PERMISSION)
async def read_complaint(
    request: Request,
    id: UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    return await service.read(id)


# CREATE ENDPOINT
@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create_complaint(
    request: Request,
    item: CreateSchema,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    Create new complaint
    
    Request Body:
    - user_type: Customer or Vendor (required)
    - vendor_id: UUID (required if user_type is Vendor)
    - customer_id: UUID (required if user_type is Customer)
    - subject_type: Block or Other (required)
    - custom_subject: Custom subject text (required if subject_type is Other)
    - complaint_date: Date of complaint (required, format: YYYY-MM-DD)
    - description: Complaint description (required)
    """
    return await service.create(request, item)


# UPDATE ENDPOINT
@router.put("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_complaint(
    request: Request,
    id: UUID,
    item: UpdateSchema,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    Update existing complaint
    
    Request Body (all optional):
    - user_type, vendor_id, customer_id, subject_type, custom_subject, complaint_date, description
    """
    return await service.update(request, id, item)


# UPDATE STATUS ENDPOINT
@router.patch("/{id}/status/", response_model=ReadSchema)
@permission_required(IN_PROGRESS_PERMISSION, CLOSE_PERMISSION)
async def update_complaint_status(
    request: Request,
    id: UUID,
    status_update: StatusUpdateSchema,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    Update complaint status (Open/In Progress/Resolved)
    
    **IMPORTANT**: If status is changed to "Approved" and subject_type is "Block",
    the associated vendor/customer will be automatically deactivated (is_active = False)
    
    Request Body:
    - status: In Progress or Resolved (required)
    """
    return await service.update_status(request, id, status_update)


# DELETE ENDPOINT
@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_complaint(
    request: Request,
    id: UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    return await service.delete(request, id)



@router.get("/all-large", response_model=ListSchema)
@permission_required()
async def list_all_complaints(
    request: Request,
    search: Optional[str] = None,
    user_type: Optional[UserTypeEnum] = None,
    status: Optional[ComplaintStatusEnum] = None,
    subject_type: Optional[SubjectTypeEnum] = None,
    vendor_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    time_period: Optional[TimePeriodEnum] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: ComplaintService = Depends(get_complaint_service)
):
    """
    List all complaints without pagination.
    Supports same filtering options as paginated list.
    """
    return await service.list_all(
        request,
        search=search,
        user_type=user_type,
        status=status,
        subject_type=subject_type,
        vendor_id=vendor_id,
        customer_id=customer_id,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/all", response_model=ComplaintListDashboard)
@permission_required()
async def list_all_complaints(
    request: Request,
    service: ComplaintService = Depends(get_complaint_service)
):
    """
    Get last 5 complaints for super fast response.
    No filters, minimal data payload.
    """
    return await service.get_last_5_complaints(request)
