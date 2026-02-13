from uuid import UUID
from datetime import date, datetime, timezone
import json, os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from core import messages
from models import Branch as Model
from sqlalchemy.orm import selectinload
from models.enums import TimePeriodEnum
from models.employee import Employee
from models.role import Role
from models.user import User
from schemas import (
    BranchList as ListSchema,
    BranchRead as ReadSchema,
    BranchCreate as CreateSchema,
    BranchUpdate as UpdateSchema,
    IdName,
)
import random
import string
from sqlalchemy import or_

from schemas.branch import AddressRead, ManagerDetails
from utils.date_helpers import get_date_range


OBJECT_NOT_FOUND = messages.BRANCH_NOT_FOUND
OBJECT_EXIST = messages.BRANCH_EXIST
OBJECT_DELETED = messages.BRANCH_DELETED


def generate_branch_code(city_name: str) -> str:
    # Take first 3 alphabetic characters from city name, uppercased and padded if needed
    letters = ''.join([c for c in city_name if c.isalpha()])[:3].upper()
    letters = letters.ljust(3, 'X')  # Pad with 'X' if less than 3 letters
    digits = ''.join(random.choices(string.digits, k=3))
    return f"{letters}{digits}"

class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        statement = (
            select(Model)
            .options(
                selectinload(Model.country),
                selectinload(Model.state),
                selectinload(Model.district),
                selectinload(Model.city),
                selectinload(Model.employees).selectinload(Employee.user).selectinload(User.role)
            )
            .where(Model.id == id)
        )
        result = await self.session.execute(statement)
        obj = result.unique().scalars().first()
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
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=OBJECT_EXIST,
            )

    async def _to_read_schema(self, obj: Model) -> ReadSchema:
        # Always reload object with eager-loaded relationships to avoid lazy loading in async context
        statement = (
            select(Model)
            .options(
                selectinload(Model.country),
                selectinload(Model.state),
                selectinload(Model.district),
                selectinload(Model.city),
                selectinload(Model.employees).selectinload(Employee.user).selectinload(User.role)
            )
            .where(Model.id == obj.id)
        )
        result = await self.session.execute(statement)
        obj = result.unique().scalars().first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        
        # Build address
        address = AddressRead(
            pin_code=obj.pin_code,
            location=obj.location,
            country=IdName(id=obj.country.id, name=obj.country.name) if obj.country else None,
            state=IdName(id=obj.state.id, name=obj.state.name) if obj.state else None,
            district=IdName(id=obj.district.id, name=obj.district.name) if obj.district else None,
            city=IdName(id=obj.city.id, name=obj.city.name) if obj.city else None,
        )
        
        # ✅ Find managers from already-loaded employees (no additional query!)
        branch_manager_data = None
        national_manager_data = None
        
        # Since we eager-loaded employees with users and roles, iterate in memory
        for employee in obj.employees:
            if not employee.is_active or not employee.user or not employee.user.is_active:
                continue
            
            role_name = employee.user.role.name.lower() if employee.user.role else ""
            
            # ✅ Branch Manager (for this branch)
            if role_name == "branch manager" and employee.branch_id == obj.id and not branch_manager_data:
                user = employee.user
                branch_manager_data = ManagerDetails(
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    name=f"{user.first_name} {user.last_name or ''}".strip() or user.email,
                    mobile=user.mobile,
                    email=user.email,
                    address=employee.address,
                    employee_pic=employee.employee_pic if employee.employee_pic else None 
                )
        
        # ✅ National Manager - need separate query (there's only one, not branch-specific)
        if not national_manager_data:
            statement = (
                select(Employee)
                .join(User, Employee.user_id == User.id)
                .join(Role, User.role_id == Role.id)
                .options(
                    selectinload(Employee.country),
                    selectinload(Employee.state),
                    selectinload(Employee.district),
                    selectinload(Employee.city),
                    selectinload(Employee.region),
                    selectinload(Employee.user)
                )
                .where(
                    func.lower(Role.name) == "national manager",
                    Employee.is_active == True,
                    User.is_active == True
                )
            )
            result = await self.session.execute(statement)
            national_manager = result.unique().scalars().first()
            
            if national_manager and national_manager.user:
                user = national_manager.user
                national_manager_data = ManagerDetails(
                    employee_id=national_manager.id,
                    employee_code=national_manager.employee_code,
                    name=f"{user.first_name} {user.last_name or ''}".strip() or user.email,
                    mobile=user.mobile,
                    email=user.email,
                    address=national_manager.address,
                    employee_pic=national_manager.employee_pic if national_manager.employee_pic else None 
                )
        
        return ReadSchema(
            id=obj.id,
            name=obj.name,
            code=obj.code,
            is_active=obj.is_active,
            email=obj.email,
            mobile=obj.mobile,
            address=address,
            branch_manager=branch_manager_data,
            national_manager=national_manager_data,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
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
        
        # Generate pagination URLs
        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None
        
        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            results=results
        )


    async def list(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        search: str | None = None, 
        country_id: UUID | None = None,   
        time_period: TimePeriodEnum | None = None,   
        start_date: date | None = None, 
        end_date: date | None = None,
        has_manager: bool | None = None,
    ) -> ListSchema:
        user = request.state.user
        """Optimized listing - only load necessary data"""
        from models import Country, State, District, City
        from sqlalchemy.orm import load_only
        
        # Build optimized query with selective loading
        base_statement = select(Model)
        
        # Filter by regional manager's region
        if user.role.name.lower() == "regional manager":
            region_name = None
            # Async query for employee
            stmt = select(Employee).where(Employee.user_id == user.id).options(selectinload(Employee.region))
            result = await self.session.execute(stmt)
            employee = result.scalars().first()

            if employee and employee.region_id:
                region_name = employee.region.name

                region_file_path = os.path.join(os.path.dirname(__file__), '..', 'region-wise-state.json')
                states_in_region = []
                try:
                    with open(region_file_path, 'r') as f:
                        region_to_states_list = json.load(f)
                        if region_to_states_list:
                            region_to_states = region_to_states_list[0]
                            states_in_region = next((states for region, states in region_to_states.items() if region.lower() == region_name.lower()), [])
                except (FileNotFoundError, json.JSONDecodeError):
                    pass 

                
                if states_in_region:
                    # Filter branches where the state name is in the list for the region
                    base_statement = base_statement.join(State).where(func.lower(State.name).in_([s.lower() for s in states_in_region]))
            # else:
                # If regional manager has no region assigned, return an empty list
                # return ListSchema(total=0, next=None, previous=None, results=[])

        # Filter by manager presence
        if has_manager is not None:
            from models import Role
            
            # Subquery to find branches that have a branch manager
            branches_with_manager_sq = (
                select(Model.id)
                .join(Employee, Model.id == Employee.branch_id)
                .join(User, Employee.user_id == User.id)
                .join(Role, User.role_id == Role.id)
                .where(
                    Role.name.ilike("branch manager"),
                    Employee.is_active == True,
                    User.is_active == True
                )
            ).distinct()
            
            if has_manager:
                base_statement = base_statement.where(Model.id.in_(branches_with_manager_sq))
            else: # has_manager is False
                base_statement = base_statement.where(Model.id.not_in(branches_with_manager_sq))


        # Apply filters
        if country_id:
            base_statement = base_statement.where(Model.country_id == country_id)
        
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
                    Model.name.ilike(f"%{search}%"),
                    Model.code.ilike(f"%{search}%"),
                    Model.pin_code.ilike(f"%{search}%"),
                    Model.location.ilike(f"%{search}%"),
                )
            )
        
        # Add options for result fetching
        statement = base_statement.options(
            selectinload(Model.country).load_only(Country.id, Country.name),
            selectinload(Model.state).load_only(State.id, State.name),
            selectinload(Model.district).load_only(District.id, District.name),
            selectinload(Model.city).load_only(City.id, City.name),
        )
        
        return await self._paginate(statement, request, page, size, base_statement=base_statement)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        obj = await self.get_object(id)
        return await self._to_read_schema(obj)

    async def create(self, request: Request, item: CreateSchema) -> ReadSchema:
        user = request.state.user
        address_data = item.address
        # Get city name for code
        city_name = None
        if address_data.city_id:
            from models import City
            stmt = select(City).where(City.id == address_data.city_id)
            result = await self.session.execute(stmt)
            city = result.scalars().first()
            if city:
                city_name = city.name
        if not city_name:
            city_name = 'XXX'
        # Generate unique branch code
        code = generate_branch_code(city_name)
        
        # Check for uniqueness asynchronously
        while True:
            stmt = select(Model).where(Model.code == code)
            result = await self.session.execute(stmt)
            if not result.scalars().first():
                break
            code = generate_branch_code(city_name)
        
        branch_data = item.dict(exclude={'address'})
        obj = Model(**branch_data, **address_data.dict(), code=code, created_by=user.id, updated_by=user.id)
        return await self._to_read_schema(await self._save(obj))

    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> ReadSchema:
        user = request.state.user
        obj = await self.get_object(id)
        
        update_data = item.dict(exclude_unset=True)
        
        if 'address' in update_data:
            address_data = update_data.pop('address')
            for key, value in address_data.items():
                setattr(obj, key, value)
                
        for key, value in update_data.items():
            setattr(obj, key, value)

        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        return await self._to_read_schema(await self._save(obj))

    async def delete(self, request: Request, id: UUID):
        obj = await self.get_object(id)
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    async def toggle_active(self, request: Request, id: UUID) -> ReadSchema:
        user = request.state.user
        obj = await self.get_object(id)
        obj.is_active = not obj.is_active
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        return await self._to_read_schema(await self._save(obj))



    async def change_branch_manager( 
        self, 
        request: Request, 
        branch_id: UUID, 
        new_manager_employee_id: UUID
    ) -> ReadSchema:
        """
        Change the branch manager with proper branch reassignment logic.
        
        Logic:
        1. New manager must have "Branch Manager" role
        2. If new manager is already a branch manager elsewhere, remove them from old branch
        3. Previous manager of current branch gets branch_id set to None
        4. All employees in current branch report to new manager
        
        Args:
            branch_id: The branch whose manager is being changed
            new_manager_employee_id: Employee ID of new manager (must have Branch Manager role)
        
        Returns:
            Updated branch details
        """
        try:
            user = request.state.user
            
            # Get the target branch
            branch = await self.get_object(branch_id)
            
            # Get the new manager employee with user and role
            stmt = (
                select(Employee)
                .options(
                    selectinload(Employee.user).selectinload(User.role),
                    selectinload(Employee.branch)
                )
                .where(Employee.id == new_manager_employee_id)
            )
            result = await self.session.execute(stmt)
            new_manager = result.unique().scalars().first()
            
            if not new_manager:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Employee with ID {new_manager_employee_id} not found"
                )
            
            if not new_manager.is_active or not new_manager.user or not new_manager.user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New manager must be an active employee with active user account"
                )
            
            # ✅ CHECK: New manager MUST have "Branch Manager" role
            role_name = new_manager.user.role.name.lower() if new_manager.user.role else ""
            if role_name != "branch manager":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected employee must have 'Branch Manager' role"
                )
            
            # Get Branch Manager role
            from models import Role
            stmt = select(Role).where(func.lower(Role.name) == "branch manager")
            result = await self.session.execute(stmt)
            branch_manager_role = result.scalars().first()
            
            if not branch_manager_role:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Branch Manager role not found in system"
                )
            
            # ✅ STEP 1: Find current branch manager of target branch
            stmt = (
                select(Employee)
                .join(User, Employee.user_id == User.id)
                .where(
                    Employee.branch_id == branch_id,
                    User.role_id == branch_manager_role.id,
                    Employee.is_active == True
                )
            )
            result = await self.session.execute(stmt)
            current_manager = result.unique().scalars().first()
            
            # ✅ STEP 2: If new manager is already managing another branch, remove them
            if new_manager.branch_id and new_manager.branch_id != branch_id:
                # Update all employees in old branch who report to this manager
                stmt = (
                    select(Employee)
                    .where(
                        Employee.branch_id == new_manager.branch_id,
                        Employee.manager_id == new_manager_employee_id
                    )
                )
                result = await self.session.execute(stmt)
                old_branch_employees = result.unique().scalars().all()
                
                for emp in old_branch_employees:
                    emp.manager_id = None
                    emp.updated_by = user.id
                    emp.updated_at = datetime.utcnow()
                    self.session.add(emp)
            
            # ✅ STEP 3: Set current manager's branch_id to None (if exists and different from new manager)
            if current_manager and current_manager.id != new_manager_employee_id:
                current_manager.branch_id = None
                current_manager.manager_id = None
                current_manager.updated_by = user.id
                current_manager.updated_at = datetime.utcnow()
                self.session.add(current_manager)
            
            # ✅ STEP 4: Assign new manager to the branch
            new_manager.branch_id = branch_id
            new_manager.manager_id = None  # Branch managers don't report to anyone in the branch
            new_manager.updated_by = user.id
            new_manager.updated_at = datetime.utcnow()
            self.session.add(new_manager)
            
            # ✅ STEP 5: Update all employees in current branch to report to new manager
            stmt = (
                select(Employee)
                .where(
                    Employee.branch_id == branch_id,
                    Employee.id != new_manager_employee_id
                )
            )
            result = await self.session.execute(stmt)
            branch_employees = result.unique().scalars().all()
            
            for emp in branch_employees:
                emp.manager_id = new_manager_employee_id
                emp.updated_by = user.id
                emp.updated_at = datetime.utcnow()
                self.session.add(emp)
            
            # Update branch audit fields
            branch.updated_by = user.id
            branch.updated_at = datetime.utcnow()
            self.session.add(branch)
            
            await self.session.commit()
            
            # Return updated branch details
            return await self._to_read_schema(branch)
            
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

