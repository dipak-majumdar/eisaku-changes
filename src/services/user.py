from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from sqlalchemy import func, or_, select
from sqlalchemy.orm import raiseload, selectinload
from core import messages
from models import User as Model
from models import Employee as EmployeeModel
from models.customer import Customer
from models.enums import TimePeriodEnum
from models.role import Role
from models.vendor import Vendor as VendorModel
from models.country import Country
from models.state import State
from models.district import District
from models.city import City
from services.notifications import NotificationService
from schemas.notifications import NotificationCreate
from schemas import (
    # UserList as ListSchema, 
    UserRead,
    UserMinimal,
    UserMinimalList
)
from sqlalchemy.orm import selectinload
from services.mail import send_email
from sqlalchemy.orm import aliased





OBJECT_NOT_FOUND = messages.USER_NOT_FOUND
OBJECT_EXIST = messages.USER_EXIST
OBJECT_DELETED = messages.USER_DELETED
PASSWORD_REQUIRED= messages.PASSWORD_REQUIRED



class Service:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def get_object(self, id: UUID) -> Model:
        result = await self.session.execute(
            select(Model)
            .options(
                selectinload(Model.role),
                selectinload(Model.vendor).options(
                    selectinload(VendorModel.branch),
                    selectinload(VendorModel.country),
                    selectinload(VendorModel.state),
                    selectinload(VendorModel.district),
                    selectinload(VendorModel.city),
                ),
                selectinload(Model.customer).options(
                    selectinload(Customer.country),
                    selectinload(Customer.state),
                    selectinload(Customer.district),
                    selectinload(Customer.city),
                ),
                selectinload(Model.employee).options(
                    selectinload(EmployeeModel.branch),
                    selectinload(EmployeeModel.manager).selectinload(EmployeeModel.user),
                    selectinload(EmployeeModel.country),
                    selectinload(EmployeeModel.state),
                    selectinload(EmployeeModel.district),
                    selectinload(EmployeeModel.city),
                    selectinload(EmployeeModel.region),
                )
            )
            .where(Model.id == id)
        )
        obj = result.scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=OBJECT_NOT_FOUND
            )
        return obj
    
    async def _save(self, obj: Model) -> Model:
        """Utility: add + commit + refresh"""
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    # services/user.py

    
    def _to_read_schema(self, obj: Model) -> UserRead:
        """Convert User model to UserRead based on role name"""
        
        # Get role info
        role_name = obj.role.name if obj.role else None
        role_id = obj.role.id if obj.role else obj.role_id
        
        address = None
        user_code = None
        branch_id = None
        branch_name = None
        manager_id = None
        manager_name = None
        employee_pic = None
        
        # ✅ Check by role name (case-insensitive, flexible matching)
        if role_name:
            role_lower = role_name.lower()
            
            if "vendor" in role_lower:
                # Get vendor data from relationship
                vendor = obj.vendor
                
                if vendor:
                    # Build address with IdName objects including branch
                    address = {
                        "country": {"id": str(vendor.country.id), "name": vendor.country.name} if vendor.country else None,
                        "state": {"id": str(vendor.state.id), "name": vendor.state.name} if vendor.state else None,
                        "district": {"id": str(vendor.district.id), "name": vendor.district.name} if vendor.district else None,
                        "city": {"id": str(vendor.city.id), "name": vendor.city.name} if vendor.city else None,
                        "branch": {"id": str(vendor.branch.id), "name": vendor.branch.name} if vendor.branch else None,
                        "pin_code": vendor.pin_code,
                        "location": vendor.location,
                    }
                    user_code = vendor.vendor_code
                    branch_id = vendor.branch.id if vendor.branch else None
                    branch_name = vendor.branch.name if vendor.branch else None
                    employee_pic = vendor.vendor_pic if hasattr(vendor, 'vendor_pic') else None
            
            elif "customer" in role_lower:
                # Get customer data from relationship
                customer = obj.customer
                
                if customer:
                    # Build address with IdName objects
                    address = {
                        "country": {"id": str(customer.country.id), "name": customer.country.name} if customer.country else None,
                        "state": {"id": str(customer.state.id), "name": customer.state.name} if customer.state else None,
                        "district": {"id": str(customer.district.id), "name": customer.district.name} if customer.district else None,
                        "city": {"id": str(customer.city.id), "name": customer.city.name} if customer.city else None,
                        "pin_code": customer.pin_code,
                        "location": customer.location,
                    }
                    user_code = customer.customer_code
                    employee_pic = customer.customer_pic if hasattr(customer, 'customer_pic') else None
            else:
                # Get employee data from relationship
                emp = obj.employee
                
                if emp:
                    # Build address with IdName objects including branch and region
                    address = {
                        "country": {"id": str(emp.country.id), "name": emp.country.name} if emp.country else None,
                        "state": {"id": str(emp.state.id), "name": emp.state.name} if emp.state else None,
                        "district": {"id": str(emp.district.id), "name": emp.district.name} if emp.district else None,
                        "city": {"id": str(emp.city.id), "name": emp.city.name} if emp.city else None,
                        "branch": {"id": str(emp.branch.id), "name": emp.branch.name} if emp.branch else None,
                        "region": {"id": str(emp.region.id), "name": emp.region.name} if emp.region else None,
                        "pin_code": emp.pin_code,
                        "location": emp.location,
                    }
                    user_code = emp.employee_code
                    branch_id = emp.branch.id if emp.branch else None
                    branch_name = emp.branch.name if emp.branch else None
                    employee_pic = emp.employee_pic
                    
                    # Manager info
                    if emp.manager:
                        manager_id = emp.manager.id
                        if emp.manager.user:
                            manager_name = f"{emp.manager.user.first_name or ''} {emp.manager.user.last_name or ''}".strip()
                            if not manager_name:
                                manager_name = emp.manager.user.email
        
        return UserRead(
            id=obj.id,
            email=obj.email,
            mobile=obj.mobile,
            first_name=obj.first_name,
            last_name=obj.last_name if obj.last_name else "",
            role_id=role_id,
            role=role_name,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            user_code=user_code,
            branch_id=branch_id,
            branch_name=branch_name,
            manager_id=manager_id,
            manager_name=manager_name,
            address=address,
            employee_pic=employee_pic,
        )

    def _to_list_schema(self, obj: Model) -> UserRead:
        """Convert User model to UserRead for listing (simplified address with just names)"""
        
        # Get role info
        role_name = obj.role.name if obj.role else None
        role_id = obj.role.id if obj.role else obj.role_id
        
        address = None
        user_code = None
        branch_id = None
        branch_name = None
        manager_id = None
        manager_name = None
        employee_pic = None
        
        # ✅ Check by role name (case-insensitive, flexible matching)
        if role_name:
            role_lower = role_name.lower()
            
            if "vendor" in role_lower:
                # Get vendor data from relationship
                vendor = obj.vendor
                
                if vendor:
                    # Build address with simple names for listing including branch
                    address = {
                        "country": vendor.country.name if vendor.country else None,
                        "state": vendor.state.name if vendor.state else None,
                        "district": vendor.district.name if vendor.district else None,
                        "city": vendor.city.name if vendor.city else None,
                        "branch": vendor.branch.name if vendor.branch else None,
                        "pin_code": vendor.pin_code,
                        "location": vendor.location,
                    }
                    user_code = vendor.vendor_code
                    branch_id = vendor.branch.id if vendor.branch else None
                    branch_name = vendor.branch.name if vendor.branch else None
                    employee_pic = vendor.vendor_pic if hasattr(vendor, 'vendor_pic') else None
            
            elif "customer" in role_lower:
                # Get customer data from relationship
                customer = obj.customer
                
                if customer:
                    # Build address with simple names for listing
                    address = {
                        "country": customer.country.name if customer.country else None,
                        "state": customer.state.name if customer.state else None,
                        "district": customer.district.name if customer.district else None,
                        "city": customer.city.name if customer.city else None,
                        "pin_code": customer.pin_code,
                        "location": customer.location,
                    }
                    user_code = customer.customer_code
                    employee_pic = customer.customer_pic if hasattr(customer, 'customer_pic') else None
            else:
                # Get employee data from relationship
                emp = obj.employee
                
                if emp:
                    # Build address with simple names for listing including branch and region
                    address = {
                        "country": emp.country.name if emp.country else None,
                        "state": emp.state.name if emp.state else None,
                        "district": emp.district.name if emp.district else None,
                        "city": emp.city.name if emp.city else None,
                        "branch": emp.branch.name if emp.branch else None,
                        "region": emp.region.name if emp.region else None,
                        "pin_code": emp.pin_code,
                        "location": emp.location,
                    }
                    user_code = emp.employee_code
                    branch_id = emp.branch.id if emp.branch else None
                    branch_name = emp.branch.name if emp.branch else None
                    employee_pic = emp.employee_pic
                    
                    # Manager info
                    if emp.manager:
                        manager_id = emp.manager.id
                        if emp.manager.user:
                            manager_name = f"{emp.manager.user.first_name or ''} {emp.manager.user.last_name or ''}".strip()
                            if not manager_name:
                                manager_name = emp.manager.user.email
        
        return UserRead(
            id=obj.id,
            email=obj.email,
            mobile=obj.mobile,
            first_name=obj.first_name,
            last_name=obj.last_name if obj.last_name else "",
            role_id=role_id,
            role=role_name,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            user_code=user_code,
            branch_id=branch_id,
            branch_name=branch_name,
            manager_id=manager_id,
            manager_name=manager_name,
            address=address,
            employee_pic=employee_pic,
        )

    def _to_minimal_schema(self, obj: Model) -> UserMinimal:
        """Convert User model to UserMinimal for fast listing with address object"""
        
        # Get role name (only name is loaded)
        role_name = obj.role.name if obj.role else None
        
        # Build address object based on user type
        address = None
        if role_name:
            role_lower = role_name.lower()
            
            if "vendor" in role_lower and obj.vendor:
                vendor = obj.vendor
                employee_pic = vendor.vendor_pic if hasattr(vendor, 'vendor_pic') else ''
                
                address = {
                    "country": vendor.country.name if vendor.country else None,
                    "state": vendor.state.name if vendor.state else None,
                    "district": vendor.district.name if vendor.district else None,
                    "city": vendor.city.name if vendor.city else None,
                    "pin_code": vendor.pin_code,
                    "location": vendor.location,
                }
                
            elif "customer" in role_lower and obj.customer:
                customer = obj.customer
                employee_pic = customer.customer_pic if hasattr(customer, 'customer_pic') else ''
                address = {
                    "country": customer.country.name if customer.country else None,
                    "state": customer.state.name if customer.state else None,
                    "district": customer.district.name if customer.district else None,
                    "city": customer.city.name if customer.city else None,
                    "pin_code": customer.pin_code,
                    "location": customer.location,
                }
            elif obj.employee:
                emp = obj.employee
                employee_pic = emp.employee_pic if hasattr(emp, 'employee_pic') else ''
                address = {
                    "country": emp.country.name if emp.country else None,
                    "state": emp.state.name if emp.state else None,
                    "district": emp.district.name if emp.district else None,
                    "city": emp.city.name if emp.city else None,
                    "pin_code": emp.pin_code,
                    "location": emp.location,
                }
        
        return UserMinimal(
            id=obj.id,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name if obj.last_name else "",
            mobile=obj.mobile,
            role=role_name or "",
            address=address,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            employee_pic=employee_pic,
        )

    # async def _paginate(self, statement, request: Request, page=1, size=10, count_statement=None) -> ListSchema:
    #     """Paginate with optimized query"""
    #     # Count total
    #     if count_statement is None:
    #         count_statement = select(func.count()).select_from(statement.subquery())
        
    #     total = (await self.session.execute(count_statement)).scalar()
        
    #     # Get paginated results
    #     offset = (page - 1) * size
    #     results = (await self.session.execute(
    #         statement.offset(offset).limit(size)
    #     )).scalars().all()

    #     next_url = (
    #         str(request.url.include_query_params(page=page + 1))
    #         if offset + size < total else None
    #     )
    #     previous_url = (
    #         str(request.url.include_query_params(page=page - 1))
    #         if page > 1 else None
    #     )

    #     read_results = [self._to_list_schema(obj) for obj in results]
    #     return ListSchema(total=total, next=next_url, previous=previous_url, results=read_results)

    async def _paginate_minimal(self, statement, request: Request, page=1, size=10, count_statement=None) -> UserMinimalList:
        """Paginate with optimized query for minimal listing"""
        # Count total
        if count_statement is None:
            count_statement = select(func.count()).select_from(statement.subquery())
        
        total = (await self.session.execute(count_statement)).scalar()
        
        # Get paginated results
        offset = (page - 1) * size
        results = (await self.session.execute(
            statement.offset(offset).limit(size)
        )).scalars().unique().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        minimal_results = [self._to_minimal_schema(obj) for obj in results]
        return UserMinimalList(total=total, next=next_url, previous=previous_url, results=minimal_results)

    # async def list(
    #     self, 
    #     request: Request, 
    #     page=1, 
    #     size=10, 
    #     search: str | None = None, 
    #     role_id: UUID | None = None,
    #     time_period: TimePeriodEnum | None = None,
    #     start_date: date | None = None,
    #     end_date: date | None = None,
    # ) -> ListSchema:
    #     """Optimized user listing"""
    #     current_user = request.state.user
    #     RoleAlias = aliased(Role)
       
    #     base_statement = (
    #         select(Model)
    #         .join(RoleAlias, Model.role_id == RoleAlias.id)
    #         .where(Model.id != current_user.id)
    #         .where(RoleAlias.name != 'admin') 
    #     )
        
    #     if role_id:
    #         base_statement = base_statement.where(Model.role_id == role_id)
        
    #     # Date filtering
    #     if start_date and end_date and not time_period:
    #         start_date = datetime.combine(start_date, datetime.min.time())
    #         end_date = datetime.combine(end_date, datetime.max.time())

    #     if start_date and end_date:
    #         base_statement = base_statement.where(Model.created_at >= start_date, Model.created_at <= end_date)
        
    #     # Search filtering
    #     if search:
    #         base_statement = base_statement.where(
    #             or_(
    #                 Model.first_name.ilike(f"%{search}%"),
    #                 Model.last_name.ilike(f"%{search}%"),
    #                 Model.username.ilike(f"%{search}%"),
    #                 Model.email.ilike(f"%{search}%"),
    #                 Model.mobile.ilike(f"%{search}%")
    #             )
    #         )
        
    #     # Optimized count statement
    #     count_statement = select(func.count()).select_from(base_statement.with_only_columns(Model.id).subquery())

    #     # Add eager loads for result fetching
    #     statement = base_statement.options(
    #         selectinload(Model.role).load_only(Role.id, Role.name),
    #         selectinload(Model.employee).options(
    #             selectinload(EmployeeModel.branch),
    #             selectinload(EmployeeModel.manager).selectinload(EmployeeModel.user),
    #             selectinload(EmployeeModel.country),
    #             selectinload(EmployeeModel.state),
    #             selectinload(EmployeeModel.district),
    #             selectinload(EmployeeModel.city),
    #             selectinload(EmployeeModel.region),
    #         ),
    #         selectinload(Model.customer).options(
    #             selectinload(Customer.country),
    #             selectinload(Customer.state),
    #             selectinload(Customer.district),
    #             selectinload(Customer.city),
    #         ),
    #         selectinload(Model.vendor).options(
    #             selectinload(VendorModel.branch),
    #             selectinload(VendorModel.country),
    #             selectinload(VendorModel.state),
    #             selectinload(VendorModel.district),
    #             selectinload(VendorModel.city),
    #         )
    #     ).order_by(Model.created_at.desc())
        
    #     return await self._paginate(statement, request, page, size, count_statement=count_statement)

    async def list_minimal(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        search: str | None = None, 
        role_id: UUID | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> UserMinimalList:
        """Optimized user listing with minimal data"""
        current_user = request.state.user
       
        base_statement = (
            select(Model)
            .where(Model.id != current_user.id)
        )
        
        if role_id:
            base_statement = base_statement.where(Model.role_id == role_id)
        
        # Date filtering
        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            base_statement = base_statement.where(Model.created_at >= start_date, Model.created_at <= end_date)
        
        # Search filtering
        if search:
            base_statement = base_statement.where(
                or_(
                    Model.first_name.ilike(f"%{search}%"),
                    Model.last_name.ilike(f"%{search}%"),
                    Model.username.ilike(f"%{search}%"),
                    Model.email.ilike(f"%{search}%"),
                    Model.mobile.ilike(f"%{search}%")
                )
            )
        
        # Optimized count statement
        count_statement = select(func.count()).select_from(base_statement.with_only_columns(Model.id).subquery())

        # Load role name and minimal address relationships for all user types
        statement = base_statement.options(
            selectinload(Model.role).load_only(Role.name),
            selectinload(Model.vendor).options(
                selectinload(VendorModel.country).load_only(Country.name),
                selectinload(VendorModel.state).load_only(State.name),
                selectinload(VendorModel.district).load_only(District.name),
                selectinload(VendorModel.city).load_only(City.name),
            ),
            selectinload(Model.customer).options(
                selectinload(Customer.country).load_only(Country.name),
                selectinload(Customer.state).load_only(State.name),
                selectinload(Customer.district).load_only(District.name),
                selectinload(Customer.city).load_only(City.name),
            ),
            selectinload(Model.employee).options(
                selectinload(EmployeeModel.country).load_only(Country.name),
                selectinload(EmployeeModel.state).load_only(State.name),
                selectinload(EmployeeModel.district).load_only(District.name),
                selectinload(EmployeeModel.city).load_only(City.name),
            ),
            raiseload('*')
        ).order_by(Model.created_at.desc())
        
        return await self._paginate_minimal(statement, request, page, size, count_statement=count_statement)

    async def read(self, request: Request, id: UUID) -> UserRead:
        obj = await self.get_object(id)
        return self._to_read_schema(obj)
    
    async def create(self, request: Request, data: dict, employee_pic=None):
        try:
            current_user = request.state.user
            user_data = data.copy()

            # Extract employee fields
            emp_fields = [
                "branch_id", "manager_id", "country_id", "state_id", "district_id", 
                "city_id", "region_id", "pin_code", "location"
            ]
            emp_data = {k: user_data.pop(k) for k in emp_fields if k in user_data}

            manager_id = emp_data.get("manager_id")
            if manager_id:
                existing_manager = (await self.session.execute(select(EmployeeModel).where(
                    EmployeeModel.id == manager_id
                ))).scalars().first()
                
                if not existing_manager:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Manager with ID {manager_id} does not exist"
                    )
            
            role_id = user_data.get("role_id")
            if role_id:
                from models import Role
                role = (await self.session.execute(select(Role).where(Role.id == role_id))).scalars().first()
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Role not found"
                    )
                
                
                if role.name.lower() == "regional manager":
                    if not emp_data.get("region_id"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Region is required for Regional Manager role"
                        )
                
                
                if role.name.lower() == "corporate admin":
                    if not emp_data.get("country_id"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Country is required for Corporate Admin role"
                        )

            
            pic_path = ''
            if employee_pic is not None and employee_pic.filename:
                import os
                upload_dir = 'uploads/employee_pics'
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{employee_pic.filename}"
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(employee_pic.file.read())
                pic_path = file_path.replace('\\', '/')
            emp_data["employee_pic"] = pic_path

            
            def generate_employee_code(city_name: str) -> str:
                letters = ''.join([c for c in city_name if c.isalpha()])[:3].upper()
                letters = letters.ljust(3, 'X')
                import random, string
                digits = ''.join(random.choices(string.digits, k=4))
                return f"{letters}{digits}"

            # Get city name for employee code generation
            city_name = None
            if emp_data.get("city_id"):
                from models import City
                city = (await self.session.execute(select(City).where(City.id == emp_data["city_id"]))).scalars().first()
                if city:
                    city_name = city.name
            if not city_name:
                city_name = 'XXX'
            
            # Ensure uniqueness
           
            code = generate_employee_code(city_name)
            while (await self.session.execute(select(EmployeeModel).where(EmployeeModel.employee_code == code))).scalars().first():
                code = generate_employee_code(city_name)
            emp_data["employee_code"] = code

            # Hash password
            raw_password = user_data.pop("password", None)
            if not raw_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=PASSWORD_REQUIRED
                )
            user_data["hashed_password"] = self.hash_password(raw_password)

            # Create user
            user_obj = Model(**user_data, created_by=current_user.id, updated_by=current_user.id)
            user_obj.username = user_obj.email
            self.session.add(user_obj)
            await self.session.commit()
            await self.session.refresh(user_obj)

            # Create employee linked to user
            emp_data["user_id"] = user_obj.id
            emp_data["created_by"] = current_user.id
            emp_data["updated_by"] = current_user.id

            employee_obj = EmployeeModel(**emp_data)
            self.session.add(employee_obj)
            await self.session.commit()
            await self.session.refresh(employee_obj)

            # Send registration email to user after user create
            header_msg="Welcome to Eisaku TMS — Your account is ready!"
            body_msg = """
                    <p>Welcome to Eisaku TMS! We’re thrilled you’ve joined us.</p>
                    <br>
                    <p>Your account has been successfully created and you can now log in and start using the platform.</p>
                """

            if not user_obj.email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User email not found")
            
            await send_email(
                session=self.session,
                request=request, 
                user=user_obj, 
                header_msg=header_msg, 
                body_msg=body_msg,
                recipient_email=user_obj.email,
                recipient_name= user_obj.name
                
            )
            
            # Create notification for new user creation
            try:
                
                notification_service = NotificationService(self.session)
                notification_data = NotificationCreate(
                    notification_type="user_created",
                    user_ids=None,  # Broadcast to all admins
                    role="admin",
                    message=f"New User '{user_obj.name}' has been created.",
                    action_required=True,
                    action_data={
                        "redirect_url": f"users/view-user/{user_obj.id}"
                    },
                )
                await notification_service.create_notification(notification_data, request)
            except Exception as notification_error:
                # Log notification error but don't fail the trip creation
                print(f" Failed to send user creation notification: {str(notification_error)}")

            
            # ✅ Re-fetch object with relationships for response
            user_obj = await self.get_object(user_obj.id)
            
            return self._to_read_schema(user_obj)
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def update(self, request: Request, id: UUID, data: dict, employee_pic=None):
        try:   
            current_user = request.state.user
            obj = await self.get_object(id)
            user_data = data.copy()

            # Validate email uniqueness if being changed
            if "email" in user_data and user_data["email"] != obj.email:
                existing_user = (await self.session.execute(
                    select(Model).where(
                        Model.email == user_data["email"],
                        Model.id != id  # Exclude current user
                    )
                )).scalars().first()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already exists"
                    )
            
            # Validate mobile uniqueness if being changed
            if "mobile" in user_data and user_data["mobile"] != obj.mobile:
                existing_user = (await self.session.execute(
                    select(Model).where(
                        Model.mobile == user_data["mobile"],
                        Model.id != id  # Exclude current user
                    )
                )).scalars().first()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mobile number already exists"
                    )

            # Extract employee fields
            emp_fields = [
                "branch_id", "manager_id", "country_id", "state_id", "district_id", 
                "city_id", "region_id", "pin_code", "location", "employee_code"
            ]
            emp_data = {k: user_data.pop(k) for k in emp_fields if k in user_data}

            # Validate manager if provided
            manager_id = emp_data.get("manager_id")
            if manager_id:
                existing_manager = (await self.session.execute(select(EmployeeModel).where(
                    EmployeeModel.id == manager_id
                ))).scalars().first()
                
                if not existing_manager:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Manager with ID {manager_id} does not exist"
                    )
            
            # Validate role if provided
            role_id = user_data.get("role_id")
            if role_id:
                from models import Role
                role = (await self.session.execute(select(Role).where(Role.id == role_id))).scalars().first()
                if not role:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Role not found"
                    )
                
                # Validate region for Regional Manager
                if role.name.lower() == "regional manager":
                    if not emp_data.get("region_id"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Region is required for Regional Manager role"
                        )
                
                # Validate country for Corporate Admin
                if role.name.lower() == "corporate admin":
                    if not emp_data.get("country_id"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Country is required for Corporate Admin role"
                        )

            # Handle file upload for employee_pic
            if employee_pic is not None and employee_pic.filename:
                import os
                upload_dir = 'uploads/employee_pics'
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{employee_pic.filename}"
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(employee_pic.file.read())
                pic_path = file_path.replace('\\', '/')
                emp_data["employee_pic"] = pic_path

            # Update user fields
            for key, value in user_data.items():
                setattr(obj, key, value)
            obj.updated_by = current_user.id
            obj.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(obj)

            # Update employee if exists
            employee_obj = (await self.session.execute(select(EmployeeModel).where(EmployeeModel.user_id == obj.id))).scalars().first()
            if employee_obj:
                for key, value in emp_data.items():
                    setattr(employee_obj, key, value)
                employee_obj.updated_by = current_user.id
                employee_obj.updated_at = datetime.utcnow()
                await self.session.commit()
                await self.session.refresh(employee_obj)
            elif emp_data:
                # If employee doesn't exist but we have employee data, create one
                emp_data["user_id"] = obj.id
                emp_data["created_by"] = current_user.id
                emp_data["updated_by"] = current_user.id
                
                # Generate employee code if needed
                if "employee_code" not in emp_data or not emp_data["employee_code"]:
                    def generate_employee_code(city_name: str) -> str:
                        letters = ''.join([c for c in city_name if c.isalpha()])[:3].upper()
                        letters = letters.ljust(3, 'X')
                        import random, string
                        digits = ''.join(random.choices(string.digits, k=4))
                        return f"{letters}{digits}"

                    # Get city name for employee code generation
                    city_name = None
                    if emp_data.get("city_id"):
                        from models import City
                        city = (await self.session.execute(select(City).where(City.id == emp_data["city_id"]))).scalars().first()
                        if city:
                            city_name = city.name
                    if not city_name:
                        city_name = 'XXX'
                    
                    # Ensure uniqueness
                    code = generate_employee_code(city_name)
                    while (await self.session.execute(select(EmployeeModel).where(EmployeeModel.employee_code == code))).scalars().first():
                        code = generate_employee_code(city_name)
                    emp_data["employee_code"] = code
                
                employee_obj = EmployeeModel(**emp_data)
                self.session.add(employee_obj)
                await self.session.commit()
                await self.session.refresh(employee_obj)

            # ✅ Re-fetch object with relationships for response
            obj = await self.get_object(obj.id)
            return self._to_read_schema(obj)
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        # Delete all employees linked to this user
        employees = (await self.session.execute(select(EmployeeModel).where(EmployeeModel.user_id == obj.id))).scalars().all()
        for emp in employees:
            await self.session.delete(emp)
        await self.session.commit()
        # Now delete the user
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    async def toggle_active(self, request: Request, id: UUID):
        try:

            user = request.state.user
            obj = await self.get_object(id)
            
            obj.is_active = not obj.is_active
            obj.updated_by = user.id
            obj.updated_at = datetime.utcnow()

            header_msg=""
            body_msg=""
            if obj.is_active:
                header_msg = "Account active"
                body_msg = "Your account has been activated."
            else:
                header_msg = "Account inactive"
                body_msg = "Your account has been deactivated."

            if not obj.email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User email not found")

            await send_email(
                session=self.session,
                request=request, 
                user=obj, 
                header_msg=header_msg, 
                body_msg=body_msg,
                recipient_email=obj.email,
                recipient_name=obj.name
            )

            return await self._save(obj)
        
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")


    async def check_exists(
        self, 
        request: Request,
        email: str | None = None, 
        mobile: str | None = None,
        exclude_user_id: UUID | None = None
    ) -> dict:
        """
        Check if email or mobile already exists across all user sources:
        - Users table
        - Customers table (email and mobile)
        - Vendors table (vendor_code@gmail.com as email)
        - Vendor Registrations table (contact_number)
        
        Args:
            email: Email to check
            mobile: Mobile number to check
            exclude_user_id: Optional user ID to exclude from check (for updates)
        
        Returns:
            dict with exists status and details
        """
        from models import User as UserModel
        from models.customer import Customer
        from models.vendor import Vendor
        from models.vendor_registation import VendorRegistration
        
        if not email and not mobile:
            return {
                "exists": False,
                "field": None,
                "message": "No email or mobile provided for checking"
            }
        
        # ============================================================
        # CHECK EMAIL
        # ============================================================
        if email:
            # 1. Check in Users table
            email_query = select(UserModel).where(UserModel.email == email)
            if exclude_user_id:
                email_query = email_query.where(UserModel.id != exclude_user_id)
            
            email_result = await self.session.execute(email_query)
            if email_result.scalars().first():
                return {
                    "exists": True,
                    "field": "email",
                    "message": f"Email '{email}' is already registered in users"
                }
            
            # 2. Check in Customers table
            customer_email_query = select(Customer).where(Customer.email == email)
            customer_email_result = await self.session.execute(customer_email_query)
            if customer_email_result.scalars().first():
                return {
                    "exists": True,
                    "field": "email",
                    "message": f"Email '{email}' is already registered as a customer"
                }
            
            # 3. Check in Vendors table (vendor_code@gmail.com format)
            # Extract vendor_code from email if it matches pattern
            if email.endswith("@gmail.com"):
                vendor_code = email.replace("@gmail.com", "")
                vendor_email_query = select(Vendor).where(Vendor.vendor_code == vendor_code)
                vendor_email_result = await self.session.execute(vendor_email_query)
                if vendor_email_result.scalars().first():
                    return {
                        "exists": True,
                        "field": "email",
                        "message": f"Email '{email}' is already registered as a vendor (vendor code: {vendor_code})"
                    }
        
        # ============================================================
        # CHECK MOBILE
        # ============================================================
        if mobile:
            # 1. Check in Users table
            mobile_query = select(UserModel).where(UserModel.mobile == mobile)
            if exclude_user_id:
                mobile_query = mobile_query.where(UserModel.id != exclude_user_id)
            
            mobile_result = await self.session.execute(mobile_query)
            if mobile_result.scalars().first():
                return {
                    "exists": True,
                    "field": "mobile",
                    "message": f"Mobile '{mobile}' is already registered in users"
                }
            
            # 2. Check in Customers table
            customer_mobile_query = select(Customer).where(Customer.mobile == mobile)
            customer_mobile_result = await self.session.execute(customer_mobile_query)
            if customer_mobile_result.scalars().first():
                return {
                    "exists": True,
                    "field": "mobile",
                    "message": f"Mobile '{mobile}' is already registered as a customer"
                }
            
            # 3. Check in Vendor Registrations table (contact_number)
            vendor_reg_mobile_query = select(VendorRegistration).where(
                VendorRegistration.contact_number == mobile
            )
            vendor_reg_mobile_result = await self.session.execute(vendor_reg_mobile_query)
            if vendor_reg_mobile_result.scalars().first():
                return {
                    "exists": True,
                    "field": "mobile",
                    "message": f"Mobile '{mobile}' is already registered in vendor registrations"
                }
        
        return {
            "exists": False,
            "field": None,
            "message": "Email and mobile are available"
        }
