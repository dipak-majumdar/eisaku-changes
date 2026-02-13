from fastapi import APIRouter, Depends, status, Request, File, UploadFile, Form, Query
from typing import Optional
from uuid import UUID
import time

from core.security import permission_required
from api.deps import get_user_service as get_service
from schemas.user import UserCheckResponse
from services import UserService as Service
from schemas import (
    UserRead as ReadSchema, 
    # UserList as ListSchema, 
    UserCreate as CreateSchema, 
    UserUpdate as UpdateSchema,
    UserMinimalList
)

CREATE_PERMISSION = 'user.can_create'
CHANGE_PERMISSION = 'user.can_change'
VIEW_PERMISSION = 'user.can_view'
DELETE_PERMISSION = 'user.can_delete'


router = APIRouter()


# @router.get("/", response_model=ListSchema)
# @permission_required(VIEW_PERMISSION)
# async def list(
#     request: Request,
#     page: int = 1,
#     size: int = 10,
#     search: str | None = None,
#     role_id: UUID | None = None, 
#     service: Service = Depends(get_service),
# ):
#     return await service.list(request, page=page, size=size, search=search,role_id=role_id)

@router.get("/", response_model=UserMinimalList)
@permission_required(VIEW_PERMISSION)
async def list_minimal(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    role_id: UUID | None = None, 
    service: Service = Depends(get_service),
):
    """Fast user listing with minimal data (id, email, role, address, status, joined_at)"""
    start_time = time.time()
    result = await service.list_minimal(request, page=page, size=size, search=search, role_id=role_id)
    end_time = time.time()
    print(f"list_minimal response time: {(end_time - start_time) * 1000:.2f}ms")
    return result


# ✅ NEW: Check duplicate email/mobile endpoint
@router.get("/check-exists", response_model=UserCheckResponse)
@permission_required()
async def check_user_exists(
    request: Request,
    email: Optional[str] = Query(None, description="Email to check for duplicates"),
    mobile: Optional[str] = Query(None, description="Mobile number to check for duplicates"),
    exclude_user_id: Optional[UUID] = Query(None, description="User ID to exclude from check (for updates)"),
    service: Service = Depends(get_service),
):
    """
    Check if email or mobile already exists in the system.
    
    Returns boolean response indicating if the credentials are already taken.
    Useful for real-time validation in registration and update forms.
    
    **Query Parameters:**
    - `email`: Email address to verify (optional)
    - `mobile`: Mobile number to verify (optional)
    - `exclude_user_id`: User ID to exclude from check - useful when updating existing users (optional)
    
    **Examples:**
    - Check email only: `GET /users/check-exists?email=john@example.com`
    - Check mobile only: `GET /users/check-exists?mobile=9876543210`
    - Check both: `GET /users/check-exists?email=john@example.com&mobile=9876543210`
    - Check for update: `GET /users/check-exists?email=john@example.com&exclude_user_id=uuid-here`
    
    **Response Examples:**
    
    Email exists:
    ```
    {
        "exists": true,
        "field": "email",
        "message": "Email 'john@example.com' is already registered"
    }
    ```
    
    Mobile exists:
    ```
    {
        "exists": true,
        "field": "mobile",
        "message": "Mobile '9876543210' is already registered"
    }
    ```
    
    Both available:
    ```
    {
        "exists": false,
        "field": null,
        "message": "Email and mobile are available"
    }
    ```
    """
    result = await service.check_exists(
        request=request,    
        email=email,
        mobile=mobile,
        exclude_user_id=exclude_user_id
    )
    return UserCheckResponse(**result)


@router.post("/", response_model=ReadSchema, status_code=status.HTTP_201_CREATED)
@permission_required(CREATE_PERMISSION)
async def create(
    request: Request,
    email: str = Form(...),
    mobile: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    role_id: UUID = Form(...),
    password: str = Form(...),
    branch_id: UUID = Form(None),
    manager_id: UUID = Form(None),
    country_id: UUID = Form(...),
    state_id: UUID = Form(...),
    district_id: UUID = Form(...),
    city_id: UUID = Form(...),
    region_id: UUID = Form(None),
    pin_code: str = Form(...),
    location: str = Form(...),
    employee_pic: UploadFile = File(None),
    service: Service = Depends(get_service)
):
    data = {
        "email": email,
        "mobile": mobile,
        "first_name": first_name,
        "last_name": last_name,
        "role_id": role_id,
        "password": password,
        "branch_id": branch_id,
        "manager_id": manager_id,
        "country_id": country_id,
        "state_id": state_id,
        "district_id": district_id,
        "city_id": city_id,
        "region_id": region_id,
        "pin_code": pin_code,
        "location": location,
    }

    # return service.create(request, data, employee_pic)

    return await service.create(request, data, employee_pic)


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
    email: str = Form(None),
    mobile: str = Form(None),
    first_name: str = Form(None),
    last_name: str = Form(None),
    role_id: UUID = Form(None),
    branch_id: UUID = Form(None),
    manager_id: UUID = Form(None),
    country_id: UUID = Form(None),
    state_id: UUID = Form(None),
    district_id: UUID = Form(None),
    city_id: UUID = Form(None),
    region_id: UUID = Form(None),
    pin_code: str = Form(None),
    location: str = Form(None),
    employee_pic: UploadFile = File(None),
    service: Service = Depends(get_service)
):
    data = {}
    
    # Only include fields that are not None
    if email is not None:
        data["email"] = email
    if mobile is not None:
        data["mobile"] = mobile
    if first_name is not None:
        data["first_name"] = first_name
    if last_name is not None:
        data["last_name"] = last_name
    if role_id is not None:
        data["role_id"] = role_id
    if branch_id is not None:
        data["branch_id"] = branch_id
    if manager_id is not None:
        data["manager_id"] = manager_id
    if country_id is not None:
        data["country_id"] = country_id
    if state_id is not None:
        data["state_id"] = state_id
    if district_id is not None:
        data["district_id"] = district_id
    if city_id is not None:
        data["city_id"] = city_id
    if region_id is not None:
        data["region_id"] = region_id
    if pin_code is not None:
        data["pin_code"] = pin_code
    if location is not None:
        data["location"] = location

    return await service.update(request, item_id, data, employee_pic)


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

