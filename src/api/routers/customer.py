from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, File, Request, Form, UploadFile, HTTPException, status,Query
from typing import List, Optional
import json

from core.security import permission_required
from api.deps import get_customer_service
from db.session import get_session
from models.enums import TimePeriodEnum
from schemas.customer import (
    ApprovedCustomerList,
    CustomerList as ListSchema,
    CustomerRead as ReadSchema,
    CustomerStatusUpdate,
    CustomerCreate,
    CustomerUpdate,
    CustomerDuplicateCheck,
    ApprovedCustomerRead
)
from services import CustomerService
from models.customer import CustomerStatusEnum,CustomerTypeEnum, CustomerAddressDocumentType, PaymentTerm
from services.vendor_registration import save_upload_file


router = APIRouter()

CREATE_PERMISSION = 'customer.can_create'
CHANGE_PERMISSION = 'customer.can_change'
VIEW_PERMISSION = 'customer.can_view'
DELETE_PERMISSION = 'customer.can_delete'
APPROVE_PERMISSION = 'customer.can_approve'
REJECT_PERMISSION = 'customer.can_reject'



@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list_customers(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    region_id: UUID | None = None,
    customer_type: CustomerTypeEnum | None = None,
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
    status: CustomerStatusEnum | None = None,
    service: CustomerService = Depends(get_customer_service),
):
    return await service.list(
        request, 
        page=page, 
        size=size, 
        search=search, 
        region_id=region_id, 
        customer_type=customer_type, 
        time_period=time_period, 
        start_date=start_date, 
        end_date=end_date, 
        status=status
        )


@router.get("/approved/", response_model=ApprovedCustomerList)
@permission_required()
async def list_approved_customers(
    request: Request,
    search: str | None = None,
    status: CustomerStatusEnum | None = None,
    service: CustomerService = Depends(get_customer_service),
):
    """
    Get a list of all approved customers.
    This endpoint does not support pagination and is intended for populating UI elements like dropdowns.
    """
    return await service.list_approved(search=search,status=status)


@router.get("/check-duplicate/", response_model=CustomerDuplicateCheck)
@permission_required(VIEW_PERMISSION)
async def check_duplicate(
    request: Request,
    gst_number: Optional[str] = None,
    pan_number: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    service: CustomerService = Depends(get_customer_service),
):
    
    if not gst_number and not pan_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of gst_number or pan_number must be provided"
        )
    
    return await service.check_duplicate(
        gst_number=gst_number,
        pan_number=pan_number,
        customer_id=customer_id
    )


@router.get("/{id}/", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_customer(
    request: Request,
    id: UUID,
    service: CustomerService = Depends(get_customer_service),
):
    return await service.read(request,id)
@router.post("/", response_model=ReadSchema)
@permission_required(CREATE_PERMISSION)

async def create_customer(
    request: Request,
    customer_name: str = Form(...),
    customer_type: CustomerTypeEnum = Form(...),
    mobile: str = Form(...),  # ✅ ADDED
    password: str = Form(...),  # ✅ ADDED
    email: Optional[str] = Form(None), 
    pin_code: str = Form(...),
    location: str = Form(...),
    country_id: UUID = Form(...),
    state_id: UUID = Form(...),
    district_id: UUID = Form(...),
    city_id: UUID = Form(...),
    payment_term: Optional[PaymentTerm] = Form(None), 
    vehicle_type_id: Optional[UUID] = Form(None), 
    address_document_type: CustomerAddressDocumentType = Form(...),
    address_document: UploadFile = File(...),
    gst_number: str = Form(...),  # CHANGED: Now required
    gst_document: UploadFile = File(...),
    pan_number: str = Form(...),  # CHANGED: Now required
    pan_document: UploadFile = File(...),
    origin_id: Optional[UUID] = Form(None),
    destination_id: Optional[UUID] = Form(None),
    tonnage: Optional[str] = Form(None),
    trip_rate: Optional[str] = Form(None),
    credit_period: int = Form(0),
    contact_persons: str = Form(..., description='A JSON string of a list of contact persons. Example: `[{"name": "John Doe", "mobile": "1234567890", "email": "john.doe@example.com"}]`'),
    agreements: str = Form(...,description='A JSON string of a list of agreements. Example: `[{"start_date": "2025-01-01", "end_date": "2026-01-01"}]`'),
    agreement_documents: Optional[List[UploadFile]] = File(None),
    service: CustomerService = Depends(get_customer_service),
):
   
    if customer_type == CustomerTypeEnum.BROKING:
        credit_period = 0
        origin_id = None
        destination_id = None
        tonnage = None
        trip_rate = None
        vehicle_type_id = None
    
    item_data = {
        "customer_name": customer_name,
        "customer_type": customer_type,
        "mobile": mobile,  # ✅ ADDED
        "password": password,  # ✅ ADDED
        "email": email,  # ✅ ADDED
        "pin_code": pin_code,
        "location": location,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
        "address_document_type": address_document_type,
        "payment_term": payment_term,
        "vehicle_type_id": vehicle_type_id,
        "gst_number": gst_number,
        "pan_number": pan_number,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "tonnage": tonnage,
        "trip_rate": trip_rate,
        "credit_period": credit_period,
    }
    
    try:
        item_data["contact_persons"] = json.loads(contact_persons)
        if not item_data["contact_persons"] or len(item_data["contact_persons"]) == 0:
            raise HTTPException(status_code=400, detail="At least one contact person is required")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON for contact_persons")
    agreements_data = []
    try:
        agreements_list = json.loads(agreements)
        if not agreements_list or len(agreements_list) == 0:
            raise HTTPException(status_code=400, detail="At least one agreement is required")
        
        for idx, ag_data in enumerate(agreements_list):
            ag_file = agreement_documents[idx] if agreement_documents and len(agreement_documents) > idx else None
            if not ag_file:
                raise HTTPException(status_code=400, detail=f"Agreement document is required for agreement {idx + 1}")
            doc_path = save_upload_file(ag_file, "uploads/agreement_documents")
            ag_data["agreement_document"] = doc_path
            agreements_data.append(ag_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON for agreements")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid agreement upload: {e}")
    
    item_data["agreements"] = agreements_data
    try:
        customer_create = CustomerCreate(**item_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return await service.create(
        request=request,
        item_data=customer_create.dict(),
        gst_document=gst_document,
        pan_document=pan_document,
        address_document=address_document,
    )


@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_customer(
    id: UUID,
    request: Request,
    service: CustomerService = Depends(get_customer_service),
):
    return await service.delete(request=request, id=id)

@router.patch("/{id}/status/", response_model=ReadSchema)
@permission_required(APPROVE_PERMISSION, REJECT_PERMISSION)
async def update_customer_status(
    request: Request,
    *,
    id: UUID,
    status_update: CustomerStatusUpdate,
    service: CustomerService = Depends(get_customer_service),
):
    return await service.update_status(
        request=request,
        id=id,
        new_status=status_update.status,
        reject_reason=status_update.reject_reason  # ADD THIS
    )

@router.put("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_customer(
    request: Request,
    id: UUID,
    customer_name: Optional[str] = Form(None),
    customer_type: Optional[CustomerTypeEnum] = Form(None),
    gst_number: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),
    origin_id: Optional[UUID] = Form(None),
    destination_id: Optional[UUID] = Form(None),
    tonnage: Optional[str] = Form(None),
    trip_rate: Optional[str] = Form(None),
    payment_term: Optional[PaymentTerm] = Form(None), 
    credit_period: Optional[int] = Form(None),
    address_document_type: Optional[CustomerAddressDocumentType] = Form(None),
    pin_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    country_id: Optional[UUID] = Form(None),
    state_id: Optional[UUID] = Form(None),
    district_id: Optional[UUID] = Form(None),
    city_id: Optional[UUID] = Form(None),
    contact_persons: Optional[str] = Form(None),
    agreements: Optional[str] = Form(None),
    vehicle_type_id: Optional[UUID] = Form(None),
    gst_document: Optional[UploadFile] = None,
    pan_document: Optional[UploadFile] = None,
    address_document: Optional[UploadFile] = None,
    agreement_documents: Optional[List[UploadFile]] = File(None),
    service: CustomerService = Depends(get_customer_service),
):
    from uuid import UUID as UUIDType
    item_data_dict = {
        "customer_name": customer_name,
        "customer_type": customer_type,
        "gst_number": gst_number,
        "pan_number": pan_number,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "tonnage": tonnage,
        "payment_term": payment_term,
        "trip_rate": trip_rate,
        "credit_period": credit_period,
        "address_document_type": address_document_type,
        "pin_code": pin_code,
        "location": location,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
        "vehicle_type_id": vehicle_type_id,
    }
    if contact_persons is not None:
        try:
            item_data_dict["contact_persons"] = json.loads(contact_persons)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for contact_persons")
    if agreements is not None:
        try:
            item_data_dict["agreements"] = json.loads(agreements)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for agreements")
    # Filter out None values
    item_data_dict = {k: v for k, v in item_data_dict.items() if v is not None}
    try:
        item_data = CustomerUpdate(**item_data_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await service.update(
        request=request,
        id=id,
        item_data=item_data,
        gst_document=gst_document,
        pan_document=pan_document,
        address_document=address_document,
        agreement_documents=agreement_documents,
    )


@router.get("/check-email/", response_model=dict)
async def check_email_availability(
    request: Request,
    email: str = Query(..., description="Email address to check"),
    service: CustomerService = Depends(get_customer_service)
):
    """
    Check if email is already taken
    
    Query Parameters:
    - email: Email address to validate
    
    Returns:
    - email: The email that was checked
    - is_available: True if email is available, False if taken
    - is_taken: True if email is taken, False if available
    
    Example Response:
    {
        "email": "john@example.com",
        "is_available": true,
        "is_taken": false
    }
    """
    return await service.check_email_availability(email)
