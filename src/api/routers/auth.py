from fastapi import APIRouter, Depends, Form, Request

from api.deps import get_auth_service as get_service, get_user_service,get_permission_service
from models.permission import Permission
from services import AuthService as Service
from services import PermissionService
from schemas import UserReadWithRole, UserRead, PermissionReadWithRequired
from dependencies.auth import login_required
from sqlalchemy.orm import Session
from schemas.branch import IdName
from api.deps import get_session
from models import Employee as EmployeeModel, Vendor as VendorModel

router = APIRouter()


class OAuth2PasswordRequestFormCustom:
    def __init__(
        self,
        identifier: str | None = Form(None),
        username: str | None = Form(None),
        password: str = Form(...),
        login_method: str = Form("mobile"),
        scope: str = Form(""),
        client_id: str | None = Form(None),
        client_secret: str | None = Form(None),
    ):
        self.identifier = identifier or username
        self.password = password
        self.login_method = login_method
        self.scopes = scope.split()
        self.client_id = client_id
        self.client_secret = client_secret


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestFormCustom = Depends(), 
    service: Service = Depends(get_service)
):
    return await service.login(
        identifier=form_data.identifier, 
        password=form_data.password,
        login_method= form_data.login_method,
        scopes=form_data.scopes
    )



@router.get("/me", response_model=UserRead)
@login_required
async def me(
    request: Request,
    service: Service = Depends(get_user_service)
):
    """
    Get current logged-in user details
    
    Returns complete user information based on role:
    - Employee: employee_code, branch, manager, address
    - Vendor: vendor_code, branch, address
    - Customer: customer_code, address
    """
    user = request.state.user
    return service._to_read_schema(user)


@router.get("/permissions")
@login_required
async def permission(request: Request, permission_service: PermissionService = Depends(get_permission_service)):
    user = request.state.user
    role = user.role
    
    from sqlalchemy import select
    result = await permission_service.session.execute(select(Permission))
    all_permissions = result.scalars().all()
    
 
    role_permission_map = {
        rp.permission_id: rp.required
        for rp in role.role_permissions
    }
    
 
    permissions = [
        PermissionReadWithRequired(
            id=perm.id,
            model_name=perm.model_name,
            action_name=perm.action_name,
            description=perm.description,
            required=role_permission_map.get(perm.id, False), 
        )
        for perm in all_permissions
    ]
    
    return permissions



@router.put("/change-password")
@login_required
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    service: Service = Depends(get_service)
):
    user = request.state.user
    return await service.reset_password(user, current_password, new_password)