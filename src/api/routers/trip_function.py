# api/routes/trip.py

from uuid import UUID
import json
from fastapi import APIRouter, Depends, Request, Form, status, Query, UploadFile, File
from typing import Optional, List
from datetime import date
from decimal import Decimal

from core.security import permission_required
from api.deps import get_trip_service
from models.enums import TimePeriodEnum
from models.trip import TripStatusEnum, GoodsTypeEnum
from schemas.trip import (
    TripList as ListSchema,
    TripRead as ReadSchema,
    TripCreate as CreateSchema,
    TripUpdate as UpdateSchema,
    TripStatusUpdate,
    AddressCreate,
    TripVendorAssign,
    TripDriverCreate,
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
CAN_ADD_SHORTAGE_DAMAGE = 'trip.can_add_shortage_damage'




# ASSIGN VENDORS TO TRIP
@router.post("/{id}/assign-vendor/", response_model=ReadSchema)
@permission_required(ASSIGN_VENDOR_PERMISSION)
async def assign_vendors_to_trip(
    request: Request,
    id: UUID,
    branch_id: UUID = Form(...),
    vendor_id: UUID = Form(...),
    vehicle_type_id: UUID = Form(...),
    tons: int = Form(...),
    vehicle_no: str = Form(...),
    insurance_expiry_date: date = Form(...),
    driver_name: str = Form(..., description="Name of the driver."),
    driver_mobile_no: str = Form(..., description="Mobile number of the driver."),
    driver_licence_no: str = Form(..., description="Licence number of the driver."),
    driver_licence_expiry: date = Form(..., description="Licence expiry date of the driver."),
    trip_rate: Decimal = Form(...),
    advance: Decimal = Form(...),
    other_charges: Decimal = Form(Decimal("0.00")),
    rc_copy: UploadFile = File(...),
    insurance_copy: UploadFile = File(...),
    service: TripService = Depends(get_trip_service),
):
    """
    Assign a vendor to a trip using form-data.
    This creates a TripVendor record and updates the trip status.
    """
    # Create a list containing a single driver from the form data.
    # This maintains compatibility with the service layer which expects a list.
    drivers_list = [
        TripDriverCreate(
            driver_name=driver_name,
            driver_mobile_no=driver_mobile_no,
            driver_licence_no=driver_licence_no,
            driver_licence_expiry=driver_licence_expiry,
        )
    ]
    item = TripVendorAssign(
        branch_id=branch_id, 
        vendor_id=vendor_id, 
        vehicle_type_id=vehicle_type_id,
        tons=tons, 
        vehicle_no=vehicle_no, 
        insurance_expiry_date=insurance_expiry_date,
        drivers=drivers_list,
        trip_rate=trip_rate, 
        advance=advance, 
        other_charges=other_charges
    )
    return await service.assign_vendor(request, id, item, rc_copy, insurance_copy)

# Add new driver to trip vendor
@router.post("/{id}/assign-vendor/add-driver/", response_model=ReadSchema)
@permission_required(ASSIGN_VENDOR_PERMISSION)
async def add_driver_to_trip_vendor(
    request: Request,
    id: UUID,
    driver_name: str = Form(..., description="Name of the driver."),
    driver_mobile_no: str = Form(..., description="Mobile number of the driver."),
    driver_licence_no: str = Form(..., description="Licence number of the driver."),
    driver_licence_expiry: date = Form(..., description="Licence expiry date of the driver."),
    service: TripService = Depends(get_trip_service),
):
    """
    Add a new driver to the assigned trip vendor.
    """
    driver = TripDriverCreate(
        driver_name=driver_name,
        driver_mobile_no=driver_mobile_no,
        driver_licence_no=driver_licence_no,
        driver_licence_expiry=driver_licence_expiry,
    )
    return await service.add_driver_to_trip_vendor(request, id, driver)

# Add vehicle loading
@router.post("/{id}/vehicle-loading/", response_model=ReadSchema)
@permission_required(LOAD_VEHICLE_PERMISSION)
async def add_vehicle_loading(
    request: Request,
    id: UUID,
    eway_bill: UploadFile = File(...),
    invoice_copy: UploadFile = File(...),
    vehicle_image: UploadFile = File(...),
    lr_copy: UploadFile = File(...),
    service: TripService = Depends(get_trip_service),
):
    """
    Add a vehicle loading to the trip.
    """
    return await service.vehicle_loading_document_upload(
        request, id, eway_bill, invoice_copy, vehicle_image, lr_copy
    )

# UPDATE VEHICLE LOADING DOCUMENTS
# @router.put("/{id}/vehicle-loading/", response_model=ReadSchema)
# @permission_required(CHANGE_PERMISSION)
# async def update_vehicle_loading(
#     request: Request,
#     id: UUID,
#     eway_bill: Optional[UploadFile] = File(None),
#     invoice_copy: Optional[UploadFile] = File(None),
#     vehicle_image: Optional[UploadFile] = File(None),
#     lr_copy: Optional[UploadFile] = File(None),
#     service: TripService = Depends(get_trip_service),
# ):
#     """
#     Update existing vehicle loading documents for a trip.
#     Only provide the files you want to replace.
#     """
#     return service.update_vehicle_loading_documents(
#         request, id, eway_bill, invoice_copy, vehicle_image, lr_copy
#     )

# ADD VEHICLE UNLOADING
@router.post("/{id}/vehicle-unloading/", response_model=ReadSchema)
@permission_required(UNLOAD_VEHICLE_PERMISSION)
async def add_vehicle_unloading(
    request: Request,
    id: UUID,
    pod_submit: Optional[UploadFile] = File(None),
    other_charges: Decimal = Form(Decimal("0.00")),
    is_shortage: Optional[bool] = Form(None),
    is_damage: Optional[bool] = Form(None),
    comments: Optional[str] = Form(None),
    service: TripService = Depends(get_trip_service),
):
    """
    Add a vehicle unloading to the trip.
    """
    return await service.add_vehicle_unloading(
        request, id, pod_submit, other_charges, is_shortage, is_damage, comments
    )


# ADD DAMAGE/SHORTAGE DETAILS
@router.post("/{id}/add-damage-shortage/", response_model=ReadSchema)
@permission_required(CAN_ADD_SHORTAGE_DAMAGE)
async def add_damage_shortage(
    request: Request,
    id: UUID,
    deducted_amount: Decimal = Form(...),
    deducted_details: str = Form(...),
    service: TripService = Depends(get_trip_service),
):
    """
    Add damage/shortage details to the trip.
    """
    return await service.add_damage_shortage(
        request, id, deducted_amount, deducted_details
    )


@router.post("/{id}/pod-send-to-customer/", response_model=ReadSchema)
@permission_required(POD_SUBMIT_PERMISSION)
async def pod_send_to_customer(
    request: Request,
    id: UUID,
    pod_submit: Optional[UploadFile] = File(None),
    send_to_customer: bool = Form(False),
    service: TripService = Depends(get_trip_service),
):
    """
    Send/attach a POD file and optionally send to customer in a single endpoint.
    - If send_to_customer=True: must include file and status must not be POD_SUBMITTED.
    - If send_to_customer=False: only file upload, status does not change.
    """
    return await service.send_pod_to_customer(request, id, pod_submit, send_to_customer)