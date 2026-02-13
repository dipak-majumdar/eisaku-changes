from datetime import date

from uuid import UUID
from fastapi import APIRouter, Depends, Request, Form, UploadFile, HTTPException, status,File,Query
from typing import List, Optional
import json
from core.security import permission_required
from api.deps import get_vendor_service
from models.enums import TimePeriodEnum
from models.vendor import VendorProfileEnum, VendorStatusEnum, VendorTypeEnum, OperationZoneEnum, AddressDocumentType
from schemas.vendor import (
    VendorList as ListSchema,
    VendorRead as ReadSchema,
    VendorStatusUpdate,
    VendorCreate,
    VendorUpdate,
    VendorDuplicateCheck,
    VendoropenList
)
from services.vendor import VendorService
from services.vendor_registration import save_upload_file

router = APIRouter()

CREATE_PERMISSION = 'vendor.can_create'
CHANGE_PERMISSION = 'vendor.can_change'
VIEW_PERMISSION = 'vendor.can_view'
DELETE_PERMISSION = 'vendor.can_delete'
APPROVE_PERMISSION = 'vendor.can_approve'
REJECT_PERMISSION = 'vendor.can_reject'




@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list_vendors(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    vendor_type: VendorTypeEnum | None = None, 
    branch_id: UUID | None = None, 
    region_id: UUID | None = None, 
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
    status: VendorStatusEnum | None = None,
    service: VendorService = Depends(get_vendor_service),
):
    return await service.list(
        request, 
        page=page, 
        size=size, 
        search=search, 
        vendor_type=vendor_type, 
        time_period=time_period, 
        start_date=start_date, 
        end_date=end_date,
        status=status, 
        branch_id=branch_id,
        region_id=region_id
        )


@router.get("/open-vendors", response_model=VendoropenList)

@permission_required()
async def list_all_vendors(
    request: Request,
    search: Optional[str] = None,
    vendor_type: Optional[VendorTypeEnum] = None,
    branch_id: Optional[UUID] = None,
    time_period: Optional[TimePeriodEnum] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[VendorStatusEnum] = None,
    service: VendorService = Depends(get_vendor_service)
):
    """Get all vendors without pagination"""
    return await service.list_all(
        request,
        search=search,
        vendor_type=vendor_type,
        branch_id=branch_id,
        time_period=time_period,
        start_date=start_date,
        end_date=end_date,
        status=status
    )


@router.get("/check-duplicate/", response_model=VendorDuplicateCheck)
@permission_required(VIEW_PERMISSION)
async def check_duplicate(
    request: Request,
    gst_number: Optional[str] = None,
    pan_number: Optional[str] = None,
    vendor_id: Optional[UUID] = None,
    service: VendorService = Depends(get_vendor_service),
):
    """
    Check if GST number or PAN number is already registered to another vendor.
    
    Query Parameters:
    - gst_number: GST number to check
    - pan_number: PAN number to check
    - vendor_id: Optional vendor ID to exclude from check (useful for update scenarios)
    
    Returns:
    - gst_duplicate: Boolean indicating if GST number is already used
    - pan_duplicate: Boolean indicating if PAN number is already used
    - gst_vendor: Details of vendor with same GST (if duplicate found)
    - pan_vendor: Details of vendor with same PAN (if duplicate found)
    """
    if not gst_number and not pan_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of gst_number or pan_number must be provided"
        )
    
    return await service.check_duplicate(
        gst_number=gst_number,
        pan_number=pan_number,
        vendor_id=vendor_id
    )

@router.get("/{id}/", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read_vendor(
    request: Request,
    id: UUID,
    service: VendorService = Depends(get_vendor_service),
):
    return await service.read(request,id)

@router.post("/", response_model=ReadSchema)
@permission_required(CREATE_PERMISSION)
async def create_vendor(
    request: Request,
    # Vendor fields
    vendor_name: str = Form(...),
    branch_id: UUID = Form(...),
    vendor_type: VendorTypeEnum = Form(...),
   
    vendor_profile: Optional[VendorProfileEnum] = Form(None),
    pin_code: str = Form(...),
    location: str = Form(...),
   
    credit_period: int = Form(0),
    origin_id: Optional[UUID] = Form(None),  
    destination_id: Optional[UUID] = Form(None), 
    operation_zone: Optional[OperationZoneEnum] = Form(None),
    route: Optional[str] = Form(None),
    registration_id: UUID = Form(...),

    # Optional Address fields
    country_id: Optional[UUID] = Form(None),
    state_id: Optional[UUID] = Form(None),
    district_id: Optional[UUID] = Form(None),
    city_id: Optional[UUID] = Form(None),
    
    
  
    vehicle_type_ids: str = Form(..., description="Comma-separated vehicle type UUIDs"), 
    # BankDetails fields
    bank_name: str = Form(...),
    ifsc_code: str = Form(...),
    account_number: str = Form(...),
    account_holder_name: str = Form(...),
    bank_document: UploadFile = File(...),
    # ContactPersons and Agreements as JSON strings
    contact_persons: Optional[str] = Form(
        None,
        description='A JSON string of a list of contact persons. Example: `[{"name": "John Doe", "mobile": "1234567890", "email": "john.doe@example.com"}]`'
    ),
    agreements: Optional[str] = Form(
        None,
        description='A JSON string of a list of agreements. Example: `[{"start_date": "2025-01-01", "end_date": "2026-01-01"}]`'
    ),
    agreement_documents: List[UploadFile] = File(...), 
    # Files
    address_document_type: AddressDocumentType = Form(...),
    address_document: UploadFile = File(...), 
    gst_number: str = Form(...),
    gst_document: UploadFile = File(...), 
    pan_number: str = Form(...),
    pan_document: UploadFile = File(...), 
     
   
    
    service: VendorService = Depends(get_vendor_service),
):
    try:
        vehicle_type_ids_list = [UUID(id_str.strip()) for id_str in vehicle_type_ids.split(',')]
        if not vehicle_type_ids_list:
            raise HTTPException(status_code=400, detail="At least one vehicle type is required")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid vehicle type IDs format: {e}")
    
    item_data = {
        "vendor_name": vendor_name,
        "branch_id": branch_id,
        "vendor_type": vendor_type,
        "address_document_type": address_document_type,
        "vendor_profile": vendor_profile,
        "pin_code": pin_code,
        "location": location,
        "gst_number": gst_number,  # CHANGED: From form data
        "pan_number": pan_number, 
        "origin_id": origin_id, 
        "destination_id": destination_id, 
        "credit_period": credit_period,
        "operation_zone": operation_zone,
        "route": route,
        "registration_id": registration_id,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
        "vehicle_type_ids": vehicle_type_ids_list,
        "bank_details": {
            "bank_name": bank_name,
            "ifsc_code": ifsc_code,
            "account_number": account_number,
            "account_holder_name": account_holder_name,
        },
    }
    if contact_persons:
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
        
        # Validate that we have the same number of agreement documents as agreements
        if not agreement_documents or len(agreement_documents) != len(agreements_list):
            raise HTTPException(
                status_code=400,
                detail=f"Expected {len(agreements_list)} agreement documents, got {len(agreement_documents) if agreement_documents else 0}"
            )
        
        for idx, ag_data in enumerate(agreements_list):
            ag_file = agreement_documents[idx]
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
        vendor_create = VendorCreate(**item_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await service.create(
        request=request,
        item_data=vendor_create.dict(),
        gst_document=gst_document,
        pan_document=pan_document,
        address_document=address_document,
        bank_document=bank_document,
    )

@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_vendor(
    request: Request,
    id: UUID,
    service: VendorService = Depends(get_vendor_service),
):
    return await service.delete(request=request, id=id)

@router.patch("/{id}/status/", response_model=ReadSchema)
@permission_required(APPROVE_PERMISSION, REJECT_PERMISSION)
async def update_vendor_status(
    request: Request,
    *,
    id: UUID,
    status_update: VendorStatusUpdate,
    service: VendorService = Depends(get_vendor_service),
):
    return await service.update_status(
        request=request,
        id=id,
        new_status=status_update.status,
        reject_reason=status_update.reject_reason  
    )
@router.patch("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_vendor(
    request: Request,
    id: UUID,
    vendor_name: Optional[str] = Form(None),
    vendor_type: Optional[VendorTypeEnum] = Form(None),
    vendor_profile: Optional[VendorProfileEnum] = Form(None),
    gst_number: Optional[str] = Form(None),
    pan_number: Optional[str] = Form(None),
    origin_id: Optional[UUID] = Form(None),  
    destination_id: Optional[UUID] = Form(None),  
    credit_period: Optional[int] = Form(None),
    operation_zone: Optional[OperationZoneEnum] = Form(None),
    route: Optional[str] = Form(None),
    address_document_type: Optional[AddressDocumentType] = Form(None),
    pin_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    country_id: Optional[UUID] = Form(None),
    state_id: Optional[UUID] = Form(None),
    district_id: Optional[UUID] = Form(None),
    city_id: Optional[UUID] = Form(None),
    
    # Bank Details fields (individual fields)
    bank_name: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    account_holder_name: Optional[str] = Form(None),
    bank_document: Optional[UploadFile] = File(None),
    
    # Contact persons and agreements (JSON strings)
    contact_persons: Optional[str] = Form(None),
    agreements: Optional[str] = Form(None),
    vehicle_type_ids: Optional[str] = Form(None),
    
    # Document files
    gst_document: Optional[UploadFile] = File(None),
    pan_document: Optional[UploadFile] = File(None),
    address_document: Optional[UploadFile] = File(None),
    agreement_documents: Optional[List[UploadFile]] = File(None),  
    service: VendorService = Depends(get_vendor_service),
):
    try:
        print(f"DEBUG - Update vendor {id}")
        print(f"DEBUG - Agreements JSON: {agreements}")
        print(f"DEBUG - Agreement documents: {agreement_documents}")
        if agreement_documents:
            print(f"DEBUG - Agreement docs count: {len(agreement_documents)}")
            for idx, doc in enumerate(agreement_documents):
                print(f"DEBUG - Doc {idx}: filename={doc.filename if doc else None}")
        
        item_data_dict = {
            "vendor_name": vendor_name,
            "vendor_type": vendor_type,
            "vendor_profile": vendor_profile,
            "gst_number": gst_number,
            "pan_number": pan_number,
            "origin_id": origin_id, 
            "destination_id": destination_id, 
            "credit_period": credit_period,
            "operation_zone": operation_zone,
            "route": route,
            "address_document_type": address_document_type,
            "pin_code": pin_code,
            "location": location,
            "country_id": country_id,
            "state_id": state_id,
            "district_id": district_id,
            "city_id": city_id,
        }

        # Build bank_details dict if any bank field is provided
        if any([bank_name, ifsc_code, account_number, account_holder_name]):
            item_data_dict["bank_details"] = {
                "bank_name": bank_name,
                "ifsc_code": ifsc_code,
                "account_number": account_number,
                "account_holder_name": account_holder_name,
            }
            # Remove None values from bank_details
            item_data_dict["bank_details"] = {k: v for k, v in item_data_dict["bank_details"].items() if v is not None}

        if contact_persons:
            try:
                parsed_contacts = json.loads(contact_persons)
                # Remove vendor_id and audit fields from each contact person
                for contact in parsed_contacts:
                    contact.pop('vendor_id', None)
                    contact.pop('created_at', None)
                    contact.pop('updated_at', None)
                    contact.pop('created_by', None)
                    contact.pop('updated_by', None)
                item_data_dict["contact_persons"] = parsed_contacts
            except json.JSONDecodeError as e:
                print(f"DEBUG - Contact persons JSON error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid JSON for contact_persons: {str(e)}")

        if agreements:
            try:
                parsed_agreements = json.loads(agreements)
                # Remove vendor_id and audit fields from each agreement
                for agreement in parsed_agreements:
                    agreement.pop('vendor_id', None)
                    agreement.pop('created_at', None)
                    agreement.pop('updated_at', None)
                    agreement.pop('created_by', None)
                    agreement.pop('updated_by', None)
                item_data_dict["agreements"] = parsed_agreements
                print(f"DEBUG - Parsed agreements: {item_data_dict['agreements']}")
            except json.JSONDecodeError as e:
                print(f"DEBUG - Agreements JSON error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid JSON for agreements: {str(e)}")

        if vehicle_type_ids:
            try:
                item_data_dict["vehicle_type_ids"] = [UUID(id_str.strip()) for id_str in vehicle_type_ids.split(',')]
            except ValueError as e:
                print(f"DEBUG - Vehicle type IDs error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid format for vehicle_type_ids: {str(e)}")

        # Filter out None values
        item_data_dict = {k: v for k, v in item_data_dict.items() if v is not None}

        try:
            item_data = VendorUpdate(**item_data_dict)
        except ValueError as e:
            print(f"DEBUG - VendorUpdate validation error: {e}")
            raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

        return await service.update(
            request=request,
            id=id,
            item_data=item_data,
            gst_document=gst_document,
            pan_document=pan_document,
            address_document=address_document,
            bank_document=bank_document,
            agreement_documents=agreement_documents,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG - Router exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")






# UPDATE CREDIT PERIOD ONLY
@router.patch("/{id}/credit-period/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_vendor_credit_period(
    request: Request,
    id: UUID,
    credit_period: int = Form(..., description="Credit period in days"),
    service: VendorService = Depends(get_vendor_service),
):
    """
    Update vendor credit period only
    
    Path Parameters:
    - id: Vendor UUID
    
    Form Data:
    - credit_period: Credit period in days (required)
    """
    return await service.update_credit_period(request, id, credit_period)


# UPDATE BANK DETAILS ONLY
@router.patch("/{id}/bank-details/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_vendor_bank_details(
    request: Request,
    id: UUID,
    bank_name: str = Form(..., description="Bank name"),
    account_number: str = Form(..., description="Account number"),
    ifsc_code: str = Form(..., description="IFSC code"),
    
    account_holder_name: str = Form(..., description="Account holder name"),
    bank_document: Optional[UploadFile] = File(None, description="Bank document (optional)"),
    service: VendorService = Depends(get_vendor_service),
):
    """
    Update vendor bank details only
    
    Path Parameters:
    - id: Vendor UUID
    
    Form Data:
    - bank_name: Bank name (required)
    - account_number: Account number (required)
    - ifsc_code: IFSC code (required)
    - branch_name: Branch name (required)
    - account_holder_name: Account holder name (required)
    - bank_document: Bank document file (optional - PDF, image, etc.)
    """
    bank_data = {
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
    
        "account_holder_name": account_holder_name,
    }
    
    return await service.update_bank_details(request, id, bank_data, bank_document)