from uuid import UUID
from fastapi import APIRouter, Depends, Request, status, Query
from datetime import date
from decimal import Decimal
from typing import Optional

from core.security import permission_required
from api.deps import get_advance_payment_service
from models.enums import TimePeriodEnum
from schemas.advance_payment import (
    AdvancePaymentList as ListSchema,
    AdvancePaymentRead as ReadSchema,
    AdvancePaymentCreate as CreateSchema,
    AdvancePaymentTripList,
    AdvancePaymentUpdate as UpdateSchema,
)
from schemas.payment_approval_history import PaymentApprovalHistoryList

from services import AdvancePaymentService


router = APIRouter()

CREATE_PERMISSION = 'advance_payment.can_create'
CHANGE_PERMISSION = 'advance_payment.can_change'
VIEW_PERMISSION = 'advance_payment.can_view'
DELETE_PERMISSION = 'advance_payment.can_delete'
ADVANCE_TRIP_APPROVE_PERMISSION = 'trip.can_approve_advance_payment'


# Trip list for advance payment
@router.get("/advance-payment-approved-trips/", response_model=AdvancePaymentTripList)
@permission_required()
async def list_advance_payment_approved_pending_trips(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    List trips pending advance payment approval    
    """
    return await service.advance_payment_approved_pending_trips(request, page=page, size=size, search=search)


# Approve trip advance payment
@router.post("/trip-advance-payments/{trip_id}/approve/", status_code=status.HTTP_200_OK)
@permission_required(ADVANCE_TRIP_APPROVE_PERMISSION)
async def approve_trip_advance_payment(
    request: Request,
    trip_id: UUID,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    Approve trip advance payment
    """
    return await service.approve_trip_advance_payment(request, trip_id)


@router.post("/trip-balance-payments/{trip_id}/approve/", status_code=status.HTTP_200_OK)
@permission_required(ADVANCE_TRIP_APPROVE_PERMISSION)
async def approve_trip_balance_payment(
    request: Request,
    trip_id: UUID,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    Approve trip balance payment
    """
    return await service.approve_trip_balance_payment(request, trip_id)


# LIST ENDPOINT
@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list_advance_payments(
    request: Request,
    page: int = 1,
    size: int = 10,
    customer_id: UUID | None = None,
    vendor_id: UUID | None = None,
    trip_id: UUID | None = None,
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
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    List advance payments with optional filters
    
    Query Parameters:
    - page: Page number (default: 1)
    - size: Items per page (default: 10)
    - customer_id: Filter by customer UUID
    - vendor_id: Filter by vendor UUID
    - trip_id: Filter by trip UUID
    """
    return await service.list(
        request, 
        page=page, 
        size=size, 
        customer_id=customer_id,
        vendor_id=vendor_id,
        trip_id=trip_id,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date
    )


# PAYMENT APPROVAL HISTORY LIST ENDPOINT
@router.get("/approval-history/", response_model=PaymentApprovalHistoryList)
@permission_required()
async def list_payment_approval_history(
    request: Request,
    page: int = 1,
    size: int = 10,
    trip_id: UUID | None = None,
    approval_type: str | None = Query(None, description="Filter by approval type: 'advance_payment' or 'balance_payment'"),
    branch_id: UUID | None = None,
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
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    List payment approval history
    
    Query Parameters:
    - page: Page number (default: 1)
    - size: Items per page (default: 10)
    - trip_id: Filter by trip UUID (optional)
    - approval_type: Filter by approval type - 'advance_payment' or 'balance_payment' (optional)
    - branch_id: Filter by branch UUID (optional)
    - time_period: Filter by time period - TODAY, THIS_WEEK, THIS_MONTH, etc. (optional)
    - start_date: Filter by start date (format: YYYY-MM-DD) (optional)
    - end_date: Filter by end date (format: YYYY-MM-DD) (optional)
    """
    return await service.list_payment_approval_history(
        request,
        page=page,
        size=size,
        trip_id=trip_id,
        approval_type=approval_type,
        branch_id=branch_id,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date
    )


# READ ENDPOINT
@router.get("/{id}/", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_advance_payment(
    request: Request,
    id: UUID,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    return await service.read(id)


# CREATE ENDPOINT
@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create_advance_payment(
    request: Request,
    item: CreateSchema,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    Create new advance payment
    
    Request Body:
    - trip_id: UUID (required)
    - date: Date (required) - Format: YYYY-MM-DD
    - utr_no: String (required) - UTR/Transaction number
    - amount: Decimal (required) - Must be greater than 0
    """
    return await service.create(request, item)


# UPDATE ENDPOINT
@router.put("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_advance_payment(
    request: Request,
    id: UUID,
    item: UpdateSchema,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    """
    Update existing advance payment
    
    Request Body (all optional):
    - trip_id: UUID
    - date: Date - Format: YYYY-MM-DD
    - utr_no: String - UTR/Transaction number
    - amount: Decimal - Must be greater than 0
    """
    return await service.update(request, id, item)


# DELETE ENDPOINT
@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_advance_payment(
    request: Request,
    id: UUID,
    service: AdvancePaymentService = Depends(get_advance_payment_service),
):
    return await service.delete(request, id)
