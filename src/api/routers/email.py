
from uuid import UUID
from fastapi import APIRouter, Request, Depends, HTTPException
from api.deps import get_email_service
from models.enums import TimePeriodEnum
from schemas.email import EmailList, EmailRead, EmailBulkDelete
from core.security import permission_required
from typing import Optional
from datetime import date
from fastapi import Query
from pydantic import ValidationError

from services.email import Service as EmailService


router = APIRouter()

# LIST - Fetches all emails from database with pagination and filtering
@router.get("/", response_model=EmailList)
@permission_required()
async def list_emails(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
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
    service: EmailService = Depends(get_email_service),
):
    return await service.list(request, page, size, search, time_period, start_date, end_date)

# READ
@router.get("/{id}", response_model=EmailRead)
@permission_required()
async def read_email(
    request: Request,
    id: UUID,
    service: EmailService = Depends(get_email_service),
):
    db_obj = await service.read(id, request)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Email not found")
    try:
        return EmailRead.model_validate(db_obj)
    except ValidationError as e:
        # Re-raising the validation error will have FastAPI return a 422 response
        raise e

# BULK DELETE
@router.delete("/bulk")
@permission_required()
async def bulk_delete_emails(
    request: Request,
    bulk_delete_request: EmailBulkDelete,
    service: EmailService = Depends(get_email_service),
):
    """Delete multiple emails at once"""
    return await service.bulk_delete(bulk_delete_request.email_ids)
