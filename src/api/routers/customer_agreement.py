from typing import Optional

from fastapi import APIRouter, Depends, status, Request, Form, File, UploadFile, Query
from uuid import UUID
from datetime import date
from core.security import permission_required
from api.deps import get_customer_agreement as get_service
from models.enums import TimePeriodEnum
from services import CustomerAgreementService as Service
from schemas import (
    CustomerAgreementRead as ReadSchema, 
    CustomerAgreementList as ListSchema, 
    CustomerAgreementCreate as CreateSchema, 
    CustomerAgreementUpdate as UpdateSchema
)

CREATE_PERMISSION = 'vendoragreeement.can_create'
CHANGE_PERMISSION = 'vendoragreeement.can_change'
VIEW_PERMISSION = 'vendoragreeement.can_view'
DELETE_PERMISSION = 'vendoragreeement.can_delete'

router = APIRouter()


@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    customer_id: UUID | None = None,
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
    return await service.list(request, page=page, size=size, search=search, customer_id=customer_id, time_period=time_period, start_date=start_date, end_date=end_date)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create(
    request: Request,
    customer_id: UUID = Form(..., description="customer UUID"),
    start_date: date = Form(..., description="Agreement start date (YYYY-MM-DD)"),
    end_date: date = Form(..., description="Agreement end date (YYYY-MM-DD)"),
    agreement_document: UploadFile = File(..., description="Agreement document file (required)"),
    service: Service = Depends(get_service)
):
    """
    Create customer agreement with document upload
    
    Form Fields:
    - customer_id: UUID of the customer (required)
    - start_date: Agreement start date (required, format: YYYY-MM-DD)
    - end_date: Agreement end date (required, format: YYYY-MM-DD)
    - agreement_document: Agreement document file (required - PDF, image, etc.)
    """
    item = CreateSchema(
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date
    )
    return await service.create(request, item, agreement_document)


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
    start_date: Optional[date] = Form(None),
    end_date: Optional[date] = Form(None),
    agreement_document: Optional[UploadFile] = File(None),
    service: Service = Depends(get_service)
):
    """
    Update vendor agreement
    
    Form Fields (all optional):
    - start_date: New start date (YYYY-MM-DD)
    - end_date: New end date (YYYY-MM-DD)
    - agreement_document: New agreement document file (optional)
    """
    update_data = {}
    if start_date is not None:
        update_data["start_date"] = start_date
    if end_date is not None:
        update_data["end_date"] = end_date
    
    item = UpdateSchema(**update_data)
    return await service.update(request, item_id, item, agreement_document)


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
