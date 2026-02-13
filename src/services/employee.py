import os
from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, func, select
from fastapi import HTTPException, Request, status, UploadFile
from sqlalchemy.exc import IntegrityError # Import UploadFile
from passlib.context import CryptContext
from core import messages
from models import Employee as Model, User as UserModel
from models.branch import Branch
from models.city import City
from models.country import Country
from models.district import District
from models.enums import TimePeriodEnum
from models.role import Role
from models.state import State
from schemas import (
    EmployeeList as ListSchema,
    EmployeeRead as ReadSchema,
    EmployeeCreate as CreateSchema,
    EmployeeUpdate as UpdateSchema, # Import UploadFile
    UserCreate as UserCreateSchema, # Import UserRead for _to_read_schema
    UserRead as UserReadSchema
)
from schemas.branch import IdName
from sqlalchemy import or_
from schemas.employee import AddressRead, EmployeeListRead
from schemas.user import UserBasic
from utils.date_helpers import get_date_range  # Import UserBasic


OBJECT_NOT_FOUND = messages.EMPLOYEE_NOT_FOUND
OBJECT_EXIST = messages.EMPLOYEE_EXIST
from sqlalchemy.orm import selectinload # Import selectinload
OBJECT_DELETED = messages.EMPLOYEE_DELETED
PASSWORD_REQUIRED = messages.PASSWORD_REQUIRED

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
                selectinload(Model.user).selectinload(UserModel.role),
                selectinload(Model.branch),
                selectinload(Model.manager).selectinload(Model.user),
                selectinload(Model.reports).selectinload(Model.user),
                selectinload(Model.country),
                selectinload(Model.state),
                selectinload(Model.district),
                selectinload(Model.city),
                selectinload(Model.region),
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

    def _to_read_schema(self, obj: Model) -> ReadSchema:
        
        address = AddressRead(
            pin_code=obj.pin_code,
            location=obj.location,
            country=IdName(id=obj.country.id, name=obj.country.name) if obj.country else None,
            state=IdName(id=obj.state.id, name=obj.state.name) if obj.state else None,
            district=IdName(id=obj.district.id, name=obj.district.name) if obj.district else None,
            city=IdName(id=obj.city.id, name=obj.city.name) if obj.city else None,
            region=IdName(id=obj.region.id, name=obj.region.name) if obj.region else None,  
    
        )
        
        # Construct UserBasic schema for the nested user object
        user_obj = obj.user
        user_basic_schema = None
        if user_obj:
            user_role = IdName(id=user_obj.role.id, name=user_obj.role.name) if user_obj.role else None
            user_basic_schema = UserBasic(
                id=user_obj.id,
                email=user_obj.email,
                mobile=user_obj.mobile,
                first_name=user_obj.first_name,
                last_name=user_obj.last_name if user_obj.last_name else "",
                role_id=user_obj.role_id,
                is_active=user_obj.is_active,
              
                role=user_role,
            )
        
        return ReadSchema(
            id=obj.id,
            employee_code=obj.employee_code,
            employee_pic=obj.employee_pic,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
            user=user_basic_schema,  # Use UserBasic
            branch=IdName(id=obj.branch.id, name=obj.branch.name) if obj.branch else None,
            manager=IdName(id=obj.manager.id, name=f"{obj.manager.user.first_name} {obj.manager.user.last_name}") if obj.manager and obj.manager.user else None,
            reports=[IdName(id=rep.id, name=f"{rep.user.first_name} {rep.user.last_name}") for rep in obj.reports if rep.user] if obj.reports else [],
            address=address,
        )

    async def _paginate(self, statement, request: Request, page=1, size=10, base_statement=None) -> ListSchema:
        """Optimized pagination for SQLAlchemy 2.0"""
        # Get total count
        if base_statement is not None:
             count_stmt = select(func.count()).select_from(base_statement.with_only_columns(Model.id).subquery())
        else:
             count_stmt = select(func.count()).select_from(statement.subquery())

        total = (await self.session.execute(count_stmt)).scalar()
        
        # Pagination
        offset = (page - 1) * size
        limit = size
        
        # Apply ordering and pagination
        statement = statement.order_by(Model.created_at.desc())
        statement = statement.offset(offset).limit(limit)
        
        # Execute and get results
        results = (await self.session.execute(statement)).unique().scalars().all()
        
       
        
        list_results = []
        for emp in results:
            # Build user IdName
            user_name = f"{emp.user.first_name} {emp.user.last_name}".strip() if emp.user else None
            user_id_name = IdName(id=emp.user.id, name=user_name) if emp.user else None
            
            # ✅ FIX: Build role IdName - check if role is loaded
            role_id_name = None
            if emp.user:
                # Ensure role relationship is loaded
                if not hasattr(emp.user, 'role') or emp.user.role is None:
                    # Refresh to load role if not already loaded
                    await self.session.refresh(emp.user, attribute_names=['role'])
                
                if emp.user.role:
                    role_id_name = IdName(id=emp.user.role.id, name=emp.user.role.name)
            
            
            manager_name = None
            if emp.manager and emp.manager.user:
                manager_name = f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip()
            manager_id_name = IdName(id=emp.manager.id, name=manager_name) if emp.manager else None
            
           
            branch_id_name = IdName(id=emp.branch.id, name=emp.branch.name) if emp.branch else None
            
            # Create EmployeeListRead
            emp_read = EmployeeListRead(
                id=emp.id,
                employee_code=emp.employee_code,
                employee_pic=emp.employee_pic,
                user=user_id_name,
                role=role_id_name,  
                branch=branch_id_name,
                manager=manager_id_name,
                address=emp.address,
                is_active=emp.is_active,
                created_at=emp.created_at,
                updated_at=emp.updated_at,
                created_by=emp.created_by,
                updated_by=emp.updated_by,
            )
            list_results.append(emp_read)
        
       
        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None
        
        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            results=list_results
        )


    async def list(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        search: str | None = None, 
        branch_id: UUID | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,  
        end_date: date | None = None,
    ) -> ListSchema:
        """Optimized listing - only load necessary data"""
        # Build optimized query
        current_user = request.state.user
        base_statement= select(Model)
        
        base_statement = base_statement.where(Model.user_id != current_user.id)
        # Apply filters
        if branch_id:
            base_statement = base_statement.where(Model.branch_id == branch_id)
        
        # Date filtering
        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)
        if start_date:
            base_statement = base_statement.where(Model.created_at >= start_date)
        if end_date:
            base_statement = base_statement.where(Model.created_at <= end_date)
        
        # Search filtering
        if search:
            from sqlalchemy import or_
            base_statement = base_statement.where(
                or_(
                    Model.employee_code.ilike(f"%{search}%"),
                    Model.pin_code.ilike(f"%{search}%"),
                    Model.user.has(UserModel.first_name.ilike(f"%{search}%")),
                    Model.user.has(UserModel.last_name.ilike(f"%{search}%")),
                     Model.user.has(
                    UserModel.role.has(Role.name.ilike(f"%{search}%"))
                ),
                )
            )
        
        # Add options for result fetching
        statement = base_statement.options(
            selectinload(Model.user).load_only(UserModel.id, UserModel.first_name, UserModel.last_name, UserModel.role_id).selectinload(UserModel.role).load_only(Role.id, Role.name), 
            selectinload(Model.branch).load_only(Branch.id, Branch.name),
            selectinload(Model.manager).load_only(Model.id).selectinload(Model.user).load_only(UserModel.first_name, UserModel.last_name),
            selectinload(Model.country).load_only(Country.id, Country.name),
            selectinload(Model.state).load_only(State.id, State.name),
            selectinload(Model.district).load_only(District.id, District.name),
            selectinload(Model.city).load_only(City.id, City.name),
        )
        
        return await self._paginate(statement, request, page, size, base_statement=base_statement)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return self._to_read_schema(obj)

    async def create(self, request: Request, data: dict, employee_pic: UploadFile | None = None) -> ReadSchema:
        """
        Create both User and Employee records.
        Auto-assigns manager if branch has an employee with "Manager" role.
        """
        try:
            current_user = request.state.user
            # ✅ CHECK IF BRANCH ALREADY HAS A BRANCH MANAGER
            role_id = data.get("role_id")
            branch_id = data.get("branch_id")
            
            if role_id and branch_id:
                from models import Role
                
                # Get the role being assigned
                role = await self.session.get(Role, role_id)
                if role and role.name.lower() == "branch manager":
                    # Check if branch already has a branch manager
                    existing_manager = (await self.session.execute(
                        select(Model)
                        .join(UserModel, Model.user_id == UserModel.id)
                        .join(Role, UserModel.role_id == Role.id)
                        .where(
                            Model.branch_id == branch_id,
                            func.lower(Role.name) == "branch manager",
                            Model.is_active == True,
                            UserModel.is_active == True
                        )
                    )).scalars().first()
                    
                    if existing_manager:
                        # Get branch name for better error message
                        branch = await self.session.get(Branch, branch_id)
                        branch_name = branch.name if branch else "this branch"
                        
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Branch '{branch_name}' already has a Branch Manager. Please choose a different role or branch."
                        )
            # Extract employee fields
            emp_fields = [
                "branch_id", "country_id", "state_id", "district_id", "city_id", "pin_code", "location","region_id"
            ]
            emp_data = {k: data.pop(k) for k in emp_fields if k in data}
            
            # Handle employee pic upload
            pic_path = ''
            if employee_pic is not None:
                import os
                upload_dir = 'uploads/employee_pics'
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{employee_pic.filename}"
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(employee_pic.file.read())
                pic_path = file_path.replace('\\', '/')
            emp_data["employee_pic"] = pic_path
            
            # Auto-generate employee_code
            def generate_employee_code(city_name: str) -> str:
                letters = ''.join([c for c in city_name if c.isalpha()])[:3].upper()
                letters = letters.ljust(3, 'X')
                import random, string
                digits = ''.join(random.choices(string.digits, k=4))
                return f"{letters}{digits}"
            
            city_name = 'XXX'
            if emp_data.get("city_id"):
                from models import City
                city = (await self.session.execute(select(City).where(City.id == emp_data["city_id"]))).scalars().first()
                if city:
                    city_name = city.name
            
            # Ensure uniqueness
            code = generate_employee_code(city_name)
            while (await self.session.execute(select(Model).where(Model.employee_code == code))).scalars().first():
                code = generate_employee_code(city_name)
            emp_data["employee_code"] = code
            
            # Hash password
            raw_password = data.pop("password", None)
            if not raw_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PASSWORD_REQUIRED
                )
            data["hashed_password"] = self.hash_password(raw_password)
            
            # Create user
            user_obj = UserModel(**data, created_by=current_user.id, updated_by=current_user.id)
            user_obj.username = user_obj.email
            self.session.add(user_obj)
            await self.session.commit()
            await self.session.refresh(user_obj)
            
            # AUTO-ASSIGN MANAGER: Find first active employee with "Manager" role in same branch
            branch_id = emp_data.get("branch_id")
            if branch_id:
                from models import Role
                # Query for employees in the same branch with "Manager" role
                manager_employee = (await self.session.execute(
                    select(Model)
                    .join(UserModel, Model.user_id == UserModel.id)
                    .join(Role, UserModel.role_id == Role.id)
                    .where(
                        Model.branch_id == branch_id,
                        Role.name == "Branch Manager",
                        Model.is_active == True,
                        UserModel.is_active == True
                    )
                )).scalars().first()
                
                if manager_employee:
                    emp_data["manager_id"] = manager_employee.id
            
            # Create employee linked to user
            emp_data["user_id"] = user_obj.id
            emp_data["created_by"] = current_user.id
            emp_data["updated_by"] = current_user.id
            employee_obj = Model(**emp_data)
            self.session.add(employee_obj)
            await self.session.commit()
            await self.session.refresh(employee_obj)
            
            # Reload with all relationships for proper schema conversion
            employee_obj = await self.get_object(employee_obj.id)
            return self._to_read_schema(employee_obj)
            
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {e}")



    async def update(self, request: Request, id: UUID, data: dict, employee_pic: UploadFile | None = None) -> ReadSchema:
        user = request.state.user
        obj = await self.get_object(id)  # Employee object

        # Separate user fields from employee fields
        user_fields = ["first_name", "last_name", "email", "mobile","region_id"]
        user_data = {k: data.pop(k) for k in user_fields if k in data}
        
        if 'address' in data:
            address_data = data.pop('address')
            for key, value in address_data.items():
                setattr(obj, key, value)

        employee_data = data  # The rest of data

        # Handle employee_pic file upload
        if employee_pic is not None:
            upload_dir = 'uploads/employee_pics'
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{employee_pic.filename}"
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, "wb") as f:
                f.write(employee_pic.file.read())
            employee_data['employee_pic'] = file_path.replace('\\', '/')

        # Update employee fields
        for key, value in employee_data.items():
            setattr(obj, key, value)
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()

        # Update user fields on the related user object
        if user_data:
            user_obj = obj.user
            if not user_obj:
                raise HTTPException(status_code=404, detail="Associated user not found for this employee.")
            
            for key, value in user_data.items():
                setattr(user_obj, key, value)
            
            if 'email' in user_data:
                user_obj.username = user_data['email']

            user_obj.updated_by = user.id
            user_obj.updated_at = datetime.utcnow()
            self.session.add(user_obj)
        
        self.session.add(obj)
        
        # CHANGED: Direct commit instead of _save
        try:
            await self.session.commit()
            await self.session.refresh(obj)
            if user_data and obj.user:
                await self.session.refresh(obj.user)
        except IntegrityError as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e.orig}")

        # Reload with all relationships for proper schema conversion
        obj = await self.get_object(obj.id)
        return self._to_read_schema(obj)


    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    
    async def toggle_active(self, request: Request, id: UUID) -> ReadSchema: # Return ReadSchema
        user = request.state.user
        obj = await self.get_object(id)
        obj.is_active = not obj.is_active
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        return self._to_read_schema(await self._save(obj)) # Return ReadSchema
