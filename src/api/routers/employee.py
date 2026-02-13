from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, status, Request, File, UploadFile, Form,Query
from uuid import UUID # Import File, UploadFile, Form
from core.security import permission_required
from api.deps import get_employee_service as get_service
from models.enums import TimePeriodEnum
from services import EmployeeService as Service
from schemas import (
    EmployeeRead as ReadSchema, 
    EmployeeList as ListSchema, 
    EmployeeCreate as CreateSchema, 
    EmployeeUpdate as UpdateSchema
)
from api.deps import get_role_service  
from services import RoleService 
from fastapi import HTTPException  

CREATE_PERMISSION = 'employee.can_create'
CHANGE_PERMISSION = 'employee.can_change'
VIEW_PERMISSION = 'employee.can_view'
DELETE_PERMISSION = 'employee.can_delete'

router = APIRouter()

@router.get("/", response_model=ListSchema)
@permission_required(VIEW_PERMISSION)
async def list(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
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
    service: Service = Depends(get_service),
):
    return await service.list(request, page=page, size=size, search=search, branch_id=branch_id, time_period=time_period, start_date=start_date, end_date=end_date)


@router.get("/{item_id}", response_model=ReadSchema)
@permission_required(VIEW_PERMISSION)
async def read(
    request: Request,
    item_id: UUID, 
    service: Service = Depends(get_service)
):
    return await service.read(request, item_id)



@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create_employee(
    request: Request,
    # User fields
    email: str = Form(...),
    mobile: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    role_id: UUID = Form(...),
    password: str = Form(...),
    
    # Employee fields
    branch_id: Optional[UUID] = Form(None),
    region_id: Optional[UUID] = Form(None), 
    # NO manager_id field here (as requested)
    
    # Address fields
    country_id: UUID = Form(...),
    state_id: UUID = Form(...),
    district_id: UUID = Form(...),
    city_id: UUID = Form(...),
    pin_code: str = Form(...),
    location: str = Form(...),
    
    # Employee pic
    employee_pic: Optional[UploadFile] = File(None),
    
    service: Service = Depends(get_service),
    role_service: RoleService = Depends(get_role_service)
):
    """
    Create a new employee (without manager_id).
    Creates both User and Employee records.
    """
    
    data = {
        "email": email,
        "mobile": mobile,
        "first_name": first_name,
        "last_name": last_name,
        "role_id": role_id,
        "password": password,
        "branch_id": branch_id,
        "region_id": region_id,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
        "pin_code": pin_code,
        "location": location,
    }
    return await service.create(request, data, employee_pic)


# UPDATE ENDPOINT (Form Data)
@router.put("/{id}/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def update_employee(
    request: Request,
    id: UUID,
    # User fields (optional for update)
    email: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    
    # Employee fields (optional for update)
    branch_id: Optional[UUID] = Form(None),
    manager_id: Optional[UUID] = Form(None),
    region_id: Optional[UUID] = Form(None), 
    
    # Address fields (optional for update)
    country_id: Optional[UUID] = Form(None),
    state_id: Optional[UUID] = Form(None),
    district_id: Optional[UUID] = Form(None),
    city_id: Optional[UUID] = Form(None),
    pin_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    
    # Employee pic (optional for update)
    employee_pic: Optional[UploadFile] = File(None),
    
    service: Service = Depends(get_service)
):
    """
    Update an existing employee.
    Only provided fields will be updated.
    """
    data = {}
    
    # User fields
    if email is not None:
        data["email"] = email
    if mobile is not None:
        data["mobile"] = mobile
    if first_name is not None:
        data["first_name"] = first_name
    if last_name is not None:
        data["last_name"] = last_name
    
    # Address fields
    address_data = {}
    if country_id is not None:
        address_data["country_id"] = country_id
    if state_id is not None:
        address_data["state_id"] = state_id
    if district_id is not None:
        address_data["district_id"] = district_id
    if city_id is not None:
        address_data["city_id"] = city_id
    if pin_code is not None:
        address_data["pin_code"] = pin_code
    if region_id is not None:  # ✅ ADDED region_id to address
        address_data["region_id"] = region_id
    if location is not None:
        address_data["location"] = location
    
    if address_data:
        data["address"] = address_data
    
    # Employee fields
    if branch_id is not None:
        data["branch_id"] = branch_id
    if manager_id is not None:
        data["manager_id"] = manager_id
    
    
    return await service.update(request, id, data, employee_pic)


# DELETE ENDPOINT
@router.delete("/{id}/", status_code=status.HTTP_204_NO_CONTENT)
@permission_required(DELETE_PERMISSION)
async def delete_employee(
    request: Request,
    id: UUID,
    service: Service = Depends(get_service)
):
    return await service.delete(request, id)


# TOGGLE ACTIVE ENDPOINT
@router.patch("/{id}/status/", response_model=ReadSchema)
@permission_required(CHANGE_PERMISSION)
async def toggle_employee_active(
    request: Request,
    id: UUID,
    service: Service = Depends(get_service)
):
    return await service.toggle_active(request, id)
