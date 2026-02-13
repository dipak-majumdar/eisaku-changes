from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Form, UploadFile,Query
from sqlmodel import Session
from typing import List, Optional
from core.security import permission_required

from api.deps import get_vendor_registration_service as  get_services
from models.enums import TimePeriodEnum
from models.vendor_registation import VendorRegistrationStatusEnum
from schemas.vendor_resigtration import (
    VendorRegistrationList as ListSchema,
    VendorRegistrationRead as ReadSchema,
    VendorRegistrationCreate as CreateSchema,
    VendorRegistrationUpdate as UpdateSchema,
    VendorRegistrationStatusUpdate,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from schemas.branch import AddressCreate
from services.vendor_registration import Service

router = APIRouter()


CREATE_PERMISSION = 'vendor_registration.can_create'
CHANGE_PERMISSION = 'vendor_registration.can_change'
VIEW_PERMISSION = 'vendor_registration.can_view'
DELETE_PERMISSION = 'vendor_registration.can_delete'



@router.get("/", response_model=ListSchema)
@permission_required()
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    status: VendorRegistrationStatusEnum | None = None,
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
    service: Service = Depends(get_services),
):
    return await service.list(request, page=page, size=size, search=search, status=status, time_period=time_period, start_date=start_date, end_date=end_date)


@router.get("/{id}", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_vendor(
    request: Request,
    id: UUID,
    service: Service = Depends(get_services),
):
    return await service.read(request, id)

@router.post("/", response_model=ReadSchema)
@permission_required(CREATE_PERMISSION)
async def create_vendor(
    request: Request,
    transporter_firm_name: str = Form(...),
    owner_name: str = Form(...),
    contact_number: str = Form(...),
    gst_number: Optional[str] = Form(None),
    gst_document: Optional[UploadFile] = None,
    pan_card_number: Optional[str] = Form(None),
    pan_card_document: Optional[UploadFile] = None,
    region_id: UUID = Form(...),
    total_vehicle_owned: int = Form(...),
    route: str = Form(...),
    visiting_card: Optional[UploadFile] = None,
    pin_code: str = Form(...),
    location: str = Form(...),
    country_id: UUID = Form(...),
    state_id: UUID = Form(...),
    district_id: UUID = Form(...),
    city_id: UUID = Form(...),
    vehicle_type_ids: str = Form(...),
    service: Service = Depends(get_services),
):
    address_data = AddressCreate(
        pin_code=pin_code,
        location=location,
        country_id=country_id,
        state_id=state_id,
        district_id=district_id,
        city_id=city_id,
    )
    
    vehicle_type_ids_list = [UUID(id_str.strip()) for id_str in vehicle_type_ids.split(',')]
    
    item = CreateSchema(
        transporter_firm_name=transporter_firm_name,
        owner_name=owner_name,
        contact_number=contact_number,
        gst_number=gst_number,
        pan_card_number=pan_card_number,
        region_id=region_id,
        total_vehicle_owned=total_vehicle_owned,
        route=route,
        address=address_data,
        vehicle_type_ids=vehicle_type_ids_list,
    )
    
    return await service.create(
        request, 
        item, 
        gst_document, 
        pan_card_document, 
        visiting_card
    )

@router.put("/{id}", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_vendor(
    request: Request,
    id: UUID,
    transporter_firm_name: Optional[str] = Form(None),
    owner_name: Optional[str] = Form(None),
    contact_number: Optional[str] = Form(None),
    gst_number: Optional[str] = Form(None),
    gst_document: Optional[UploadFile] = None,
    pan_card_number: Optional[str] = Form(None),
    pan_card_document: Optional[UploadFile] = None,
    region_id: Optional[UUID] = Form(None),
    total_vehicle_owned: Optional[int] = Form(None),
    route: Optional[str] = Form(None),
    visiting_card: Optional[UploadFile] = None,
    pin_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    country_id: Optional[UUID] = Form(None),
    state_id: Optional[UUID] = Form(None),
    district_id: Optional[UUID] = Form(None),
    city_id: Optional[UUID] = Form(None),
    vehicle_type_ids: Optional[str] = Form(None),
    service: Service = Depends(get_services),
):
    update_data = {
        "transporter_firm_name": transporter_firm_name,
        "owner_name": owner_name,
        "contact_number": contact_number,
        "gst_number": gst_number,
        "pan_card_number": pan_card_number,
        "region_id": region_id,
        "total_vehicle_owned": total_vehicle_owned,
        "route": route,
    }
    
    if vehicle_type_ids:
        update_data["vehicle_type_ids"] = [UUID(id_str.strip()) for id_str in vehicle_type_ids.split(',')]
    
    address_data = {
        "pin_code": pin_code,
        "location": location,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
    }
    
    if any(address_data.values()):
        update_data["address"] = {k: v for k, v in address_data.items() if v is not None}
        
    item = UpdateSchema(**{k: v for k, v in update_data.items() if v is not None})
    
    return await service.update(
        request, 
        id, 
        item, 
        gst_document, 
        pan_card_document, 
        visiting_card
    )

@router.patch("/{id}/status", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_status(
    request: Request,
    id: UUID,
    item: VendorRegistrationStatusUpdate,
    service: Service = Depends(get_services),
):
    return await service.update_status(request, id, item)

@router.delete("/{id}", status_code=204)
@permission_required(DELETE_PERMISSION)
async def delete_vendor(
    request: Request,
    id: UUID,
    service: Service = Depends(get_services),
):
    await service.delete(request, id)
    return

@router.post("/check-duplicate-gst-pan/", response_model=DuplicateCheckResponse)
@permission_required(VIEW_PERMISSION)
async def check_duplicate_gst_pan(
    request: Request,
    item: DuplicateCheckRequest,
    service: Service = Depends(get_services),
):
    return await service.check_duplicate(item)

