
from decimal import Decimal
import random

from uuid import UUID
from datetime import datetime, date, timedelta
from typing import Optional, Union
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.future import select as async_select
from models import State, District, City
from models.complaint import Complaint as Model, ComplaintStatusEnum, SubjectTypeEnum, UserTypeEnum
from models.complaint_history import ComplaintStatusHistory
from models import Customer, Vendor, User
from models.country import Country
from models.employee import Employee
from schemas.complaint import (
    ComplaintList as ListSchema,
    ComplaintListDashboard,
    ComplaintListOptimized,
    ComplaintRead as ReadSchema,
    ComplaintDetailRead,
    ComplaintCreate as CreateSchema,
    ComplaintStatistics,
    ComplaintUpdate as UpdateSchema,
    ComplaintStatusUpdate as StatusUpdateSchema,
    IdNameCode,
    StatusTimeline,
    StatusTimelineItem,
    TripUserDetails,
    UpcomingTripItem,
    UserWithAddress,
     CreatedByUser, 
)
from schemas.branch import IdName
from models.enums import TimePeriodEnum
from utils.date_helpers import get_date_range

OBJECT_NOT_FOUND = "Complaint not found"
OBJECT_DELETED = "Complaint deleted successfully"

class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_customer_balance(self, customer_id: UUID) -> Decimal:
        from models.trip import Trip

        stmt = select(
            func.coalesce(
                func.sum(Trip.trip_rate + Trip.loading_unloading_charges),
                0
            ).label("total_charges"),
            func.coalesce(
                func.sum(Trip.deducted_amount),
                0
            ).label("total_deductions"),
        ).where(Trip.customer_id == customer_id)

        result = await self.session.execute(stmt)
        row = result.one()
        total_charges = Decimal(row.total_charges or 0)
        total_deductions = Decimal(row.total_deductions or 0)

        # Balance = charges - deductions
        return total_charges - total_deductions

    async def _get_vendor_balance(self, vendor_id: UUID) -> Decimal:
        from models.trip import TripVendor, Trip

        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        TripVendor.trip_rate
                        + TripVendor.other_charges
                        + TripVendor.other_unloading_charges
                    ),
                    0
                ).label("total_charges"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Trip.is_advance_given == True,
                                TripVendor.advance,
                            ),
                            else_=0,
                        )
                    ),
                    0
                ).label("total_advance"),
            )
            .join(Trip, TripVendor.trip_id == Trip.id)
            .where(TripVendor.vendor_id == vendor_id)
        )

        result = await self.session.execute(stmt)
        row = result.one()
        total_charges = Decimal(row.total_charges or 0)
        total_advance = Decimal(row.total_advance or 0)

        # Balance = charges - advance
        return total_charges - total_advance
    
    async def get_object(self, id: UUID, load_history: bool = False) -> Model:
        """Get complaint by ID with optional relationships"""
        from sqlalchemy import select
        
        stmt = select(Model).where(Model.id == id).options(
            selectinload(Model.customer).selectinload(Customer.country),
            selectinload(Model.customer).selectinload(Customer.state),
            selectinload(Model.customer).selectinload(Customer.district),
            selectinload(Model.customer).selectinload(Customer.city),
            selectinload(Model.vendor).selectinload(Vendor.country),
            selectinload(Model.vendor).selectinload(Vendor.state),
            selectinload(Model.vendor).selectinload(Vendor.district),
            selectinload(Model.vendor).selectinload(Vendor.city),
        )
        
        # ✅ Only load history when needed (detail view)
        if load_history:
            stmt = stmt.options(
                selectinload(Model.status_history).selectinload(ComplaintStatusHistory.changed_by_user)
            )
        
        result = await self.session.execute(stmt)
        obj = result.unique().scalar_one_or_none()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        return obj
    async def _get_statistics(self, base_stmt):
        """Calculate complaint statistics - OPTIMIZED"""
        # ✅ Use single query with CASE statements for counting
        stats_stmt = base_stmt.with_only_columns(
            func.count(Model.id).label('total'),
            func.sum(case((Model.status == ComplaintStatusEnum.OPEN, 1), else_=0)).label('open'),
            func.sum(case((Model.status == ComplaintStatusEnum.INPROGRESS, 1), else_=0)).label('inprogress'),
            func.sum(case((Model.status == ComplaintStatusEnum.CLOSED, 1), else_=0)).label('closed')
        ).order_by(None)
        
        result = await self.session.execute(stats_stmt)
        stats = result.one()
        
        return ComplaintStatistics(
            total=stats.total or 0,
            open=stats.open or 0,
            inprogress=stats.inprogress or 0,
            closed=stats.closed or 0
        )

    def _build_user_details(
        self, 
        obj: Model, 
        include_address: bool = False
    ) -> tuple[Optional[Union[IdNameCode, UserWithAddress]], Optional[Union[IdNameCode, UserWithAddress]]]:
        """Extract vendor and customer details (with optional address)"""
        from schemas.complaint import UserWithAddress
        
        vendor = None
        customer = None
        
        if obj.vendor:
            if include_address:
                vendor = UserWithAddress(
                    id=obj.vendor.id,
                    name=obj.vendor.vendor_name,
                    code=obj.vendor.vendor_code, 
                    address=obj.vendor.address
                )
            else:
                vendor = IdNameCode(id=obj.vendor.id, name=obj.vendor.vendor_name, code=obj.vendor.vendor_code )
        
        if obj.customer:
            if include_address:
                customer = UserWithAddress(
                    id=obj.customer.id,
                    name=obj.customer.customer_name,
                    code=obj.customer.customer_code,
                    address=obj.customer.address
                )
            else:
                customer = IdNameCode(id=obj.customer.id, name=obj.customer.customer_name,code=obj.customer.customer_code,)
        
        return vendor, customer
    async def _get_created_by_user(self, created_by_id: Optional[UUID]) -> Optional[CreatedByUser]:
        """Get user details with employee code for created_by"""
        if not created_by_id:
            return None
        
        # Query user with employee relationship
        user_stmt = select(User).where(User.id == created_by_id)
        result = await self.session.execute(user_stmt)
        user = result.unique().scalar_one_or_none()
        
        if not user:
            return None
        
        # Build user name
        user_name = f"{user.first_name} {user.last_name}".strip()
        if not user_name:
            user_name = user.email
        
        # Get employee code if exists
        employee_stmt = select(Employee).where(
            Employee.user_id == user.id,
            Employee.is_active == True
        )
        emp_result = await self.session.execute(employee_stmt)
        employee = emp_result.unique().scalar_one_or_none()
        
        employee_code = employee.employee_code if employee else None
        
        return CreatedByUser(
            id=user.id,
            name=user_name,
            code=employee_code
        )
    async def _to_read_schema(self, obj: Model) -> ReadSchema:
        """Convert model to read schema (for list - lightweight)"""
        vendor, customer = self._build_user_details(obj, include_address=False)
        created_by_user = await self._get_created_by_user(obj.created_by)
        return ReadSchema(
            id=obj.id,
            user_type=obj.user_type,
            status=obj.status,
            subject_type=obj.subject_type,
            custom_subject=obj.custom_subject,
            complaint_date=obj.complaint_date,
            description=obj.description,
            code=obj.code, 
            vendor=vendor,
            customer=customer,
            created_by_user=created_by_user, 
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
         
            updated_by=obj.updated_by,
        )

    def _build_status_timeline(self, obj: Model) -> StatusTimeline:
        """Build status timeline from history"""
        timeline_items = []
        
        for history in obj.status_history:
            changed_by_name = None
            if history.changed_by_user:
                changed_by_name = f"{history.changed_by_user.first_name} {history.changed_by_user.last_name}".strip()
                if not changed_by_name:
                    changed_by_name = history.changed_by_user.email
            
            timeline_items.append(StatusTimelineItem(
                status=history.status,
                changed_at=history.changed_at,
                changed_by=history.changed_by,
                changed_by_name=changed_by_name,
                remarks=history.remarks
            ))
        
        return StatusTimeline(
            current_status=obj.status,
            timeline=timeline_items
        )

    def _generate_random_balance(self) -> Decimal:
        """Generate random balance (0 or some value)"""
        balances = [
            Decimal("0"),
            Decimal("5000"),
            Decimal("10000"),
            Decimal("15000"),
            Decimal("20000"),
            Decimal("25000"),
            Decimal("30000"),
        ]
        return random.choice(balances)

    async def _get_upcoming_trips(self, complaint: Model) -> list[UpcomingTripItem]:
        """
        Get upcoming trips for the complaint's user (vendor or customer).
        Returns trips with status PENDING, APPROVED, or VENDOR_ASSIGNED.
        """
        from models.trip import Trip, TripStatusEnum
        from models.branch import Branch
        
        today = date.today()
        
        # Build query based on user type
        if complaint.user_type == UserTypeEnum.VENDOR and complaint.vendor_id:
            # Get trips where vendor is assigned
            from models.trip import TripVendor
            stmt = (
                select(Trip)
                .join(Trip.assigned_vendor)
                .join(Branch, Trip.branch_id == Branch.id)
                .options(
                    selectinload(Trip.assigned_vendor).selectinload(TripVendor.vendor),
                    selectinload(Trip.branch),
                    selectinload(Trip.customer)
                )
                .where(
                    TripVendor.vendor_id == complaint.vendor_id,
                    Trip.trip_date >= today,
                    Trip.status.in_([
                        TripStatusEnum.VENDOR_ASSIGNED,
                        TripStatusEnum.DRIVER_ASSIGNED,
                        TripStatusEnum.VEHICLE_LOADED
                    ])
                )
                .order_by(Trip.trip_date.asc())
                .limit(5)
            )
        elif complaint.user_type == UserTypeEnum.CUSTOMER and complaint.customer_id:
            # Get trips for this customer
            stmt = (
                select(Trip)
                .join(Branch, Trip.branch_id == Branch.id)
                .options(
                    selectinload(Trip.customer),
                    selectinload(Trip.branch)
                )
                .where(
                    Trip.customer_id == complaint.customer_id,
                    Trip.trip_date >= today,
                    Trip.status.in_([
                        TripStatusEnum.PENDING,
                        TripStatusEnum.APPROVED,
                        TripStatusEnum.VENDOR_ASSIGNED
                    ])
                )
                .order_by(Trip.trip_date.asc())
                .limit(5)
            )
        else:
            return []
        
        result = await self.session.execute(stmt)
        trips = result.unique().scalars().all()
        
        # Build response
        trip_results = []
        for trip in trips:
            # Get user name based on type
            if complaint.user_type == UserTypeEnum.VENDOR:
                user_name = trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "N/A"
                user_code = trip.assigned_vendor.vendor.vendor_code if trip.assigned_vendor else "N/A"
            else:
                user_name = trip.customer.customer_name
                user_code = trip.customer.customer_code
            
            trip_results.append(UpcomingTripItem(
                user_details=TripUserDetails(
                    name=user_name,
                    code=user_code,
                    branch=trip.branch.name
                ),
                trip_date=trip.trip_date,
                created_at=trip.created_at,
                status=trip.status.value
            ))
        print(trip_results)
        return trip_results


    async def _to_detail_schema(self, obj: Model) -> ComplaintDetailRead:
        vendor, customer = self._build_user_details(obj, include_address=True)
        status_timeline = self._build_status_timeline(obj)
        created_by_user = await self._get_created_by_user(obj.created_by)

        balance = Decimal("0.00")
        if obj.user_type == UserTypeEnum.VENDOR and obj.vendor_id:
            balance = await self._get_vendor_balance(obj.vendor_id)
            # Optional: cache into instance so property returns it
            if obj.vendor:
                obj.vendor._balance_value = balance
        elif obj.user_type == UserTypeEnum.CUSTOMER and obj.customer_id:
            balance = await self._get_customer_balance(obj.customer_id)
            if obj.customer:
                obj.customer._balance_value = balance

        upcoming_trips = await self._get_upcoming_trips(obj)

        return ComplaintDetailRead(
            id=obj.id,
            user_type=obj.user_type,
            status=obj.status,
            subject_type=obj.subject_type,
            custom_subject=obj.custom_subject,
            complaint_date=obj.complaint_date,
            description=obj.description,
            code=obj.code,
            vendor=vendor,
            customer=customer,
            created_by_user=created_by_user,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            updated_by=obj.updated_by,
            status_timeline=status_timeline,
            balance=balance,
            upcoming_trips=upcoming_trips,
        )

    async def _paginate(self, statement, request: Request, page=1, size=10, stats_statement=None) -> ListSchema:
        # Calculate stats and total at once
        count_stmt = select(func.count()).select_from(statement.alias())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar()
        
        offset = (page - 1) * size
        statement = statement.order_by(Model.created_at.desc()).offset(offset).limit(size)
        
        result = await self.session.execute(statement)
        results = result.unique().scalars().all()
        
        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None
        
        stats_query = stats_statement if stats_statement is not None else select(Model)
        stats = await self._get_statistics(stats_query)
        converted_results = [await self._to_read_schema(obj) for obj in results]
        
        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            results=converted_results,
            statistics=stats
        )




    async def list(
    self,
    request: Request,
    page: int = 1,
    size: int = 10,
    search: str | None = None,
    user_type: Optional[UserTypeEnum] = None,
    status: Optional[ComplaintStatusEnum] = None,
    subject_type: Optional[SubjectTypeEnum] = None,
    vendor_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    time_period: Optional[TimePeriodEnum] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    ) -> ListSchema:
        statement = select(Model).options(
            # Customer block
            joinedload(Model.customer)
                .load_only(
                    Customer.customer_name,
                    Customer.customer_code,
                    Customer.pin_code,
                    Customer.location,
                    Customer.country_id,
                    Customer.state_id,
                    Customer.district_id,
                    Customer.city_id,
                ),
            joinedload(Model.customer).joinedload(Customer.country).load_only(Country.name),
            joinedload(Model.customer).joinedload(Customer.state).load_only(State.name),
            joinedload(Model.customer).joinedload(Customer.district).load_only(District.name),
            joinedload(Model.customer).joinedload(Customer.city).load_only(City.name),

            # Vendor block
            joinedload(Model.vendor)
                .load_only(
                    Vendor.vendor_name,
                    Vendor.vendor_code,
                    Vendor.pin_code,
                    Vendor.location,
                    Vendor.country_id,
                    Vendor.state_id,
                    Vendor.district_id,
                    Vendor.city_id,
                ),
            joinedload(Model.vendor).joinedload(Vendor.country).load_only(Country.name),
            joinedload(Model.vendor).joinedload(Vendor.state).load_only(State.name),
            joinedload(Model.vendor).joinedload(Vendor.district).load_only(District.name),
            joinedload(Model.vendor).joinedload(Vendor.city).load_only(City.name),
        )

        # Create a separate statement for statistics that only includes scope filters (not search/status/etc)
        stats_statement = select(Model)
        
        user = request.state.user
        if user and user.role:
            role_name = user.role.name.lower()
            
            if role_name == "customer":
                customer_stmt = select(Customer).where(Customer.user_id == user.id)
                cust_result = await self.session.execute(customer_stmt)
                customer = cust_result.unique().scalar_one_or_none()
                if customer:
                    statement = statement.where(Model.customer_id == customer.id)
                    stats_statement = stats_statement.where(Model.customer_id == customer.id)
            elif role_name == "vendor":
                vendor_stmt = select(Vendor).where(Vendor.user_id == user.id)
                vend_result = await self.session.execute(vendor_stmt)
                vendor = vend_result.unique().scalar_one_or_none()
                if vendor:
                    statement = statement.where(Model.vendor_id == vendor.id)
                    stats_statement = stats_statement.where(Model.vendor_id == vendor.id)
        if search:
            statement = statement.where(
                or_(
                    Model.vendor.has(Vendor.vendor_name.ilike(f"%{search}%")),
                    Model.customer.has(Customer.customer_name.ilike(f"%{search}%"))
                )
            )
        if user_type:
            statement = statement.where(Model.user_type == user_type)
        if status:
            statement = statement.where(Model.status == status)
        if subject_type:
            statement = statement.where(Model.subject_type == subject_type)
        if vendor_id:
            statement = statement.where(Model.vendor_id == vendor_id)
        if customer_id:
            statement = statement.where(Model.customer_id == customer_id)
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            statement = statement.where(Model.created_at >= date_start)
        if date_end:
            statement = statement.where(Model.created_at <= date_end)
        return await self._paginate(statement, request, page, size, stats_statement=stats_statement)

    async def get_last_5_complaints(self, request: Request) -> ComplaintListDashboard:
        """Get last 5 complaints for fast response - no filters, minimal data"""
        user = request.state.user
        
        # Build minimal query with only essential fields
        statement = select(Model).options(
            # Minimal customer loading - only name and code
            joinedload(Model.customer).load_only(
                Customer.customer_name,
                Customer.customer_code,
            ),
            # Minimal vendor loading - only name and code  
            joinedload(Model.vendor).load_only(
                Vendor.vendor_name,
                Vendor.vendor_code,
            ),
        ).order_by(Model.created_at.desc()).limit(5)
        
        # Apply role-based filtering if needed
        if user and user.role:
            role_name = user.role.name.lower()
            
            if role_name == "customer":
                customer_stmt = select(Customer.id).where(Customer.user_id == user.id)
                cust_result = await self.session.execute(customer_stmt)
                customer_id_filter = cust_result.scalar_one_or_none()
                if customer_id_filter:
                    statement = statement.where(Model.customer_id == customer_id_filter)
                else:
                    return ComplaintListDashboard(results=[], statistics={})
            elif role_name == "vendor":
                vendor_stmt = select(Vendor.id).where(Vendor.user_id == user.id)
                vend_result = await self.session.execute(vendor_stmt)
                vendor_id_filter = vend_result.scalar_one_or_none()
                if vendor_id_filter:
                    statement = statement.where(Model.vendor_id == vendor_id_filter)
                else:
                    return ComplaintListDashboard(results=[], statistics={})
        
        # Execute query
        result = await self.session.execute(statement)
        results = result.unique().scalars().all()
        
        # Calculate proper statistics using the optimized function
        statistics = await self._get_statistics(statement)
        
        # Convert to minimal schema
        minimal_results = []
        for obj in results:
            customer_data = None
            vendor_data = None
            
            if obj.customer:
                customer_data = IdNameCode(
                    id=obj.customer.id,
                    name=obj.customer.customer_name,
                    code=obj.customer.customer_code
                )
            
            if obj.vendor:
                vendor_data = IdNameCode(
                    id=obj.vendor.id,
                    name=obj.vendor.vendor_name,
                    code=obj.vendor.vendor_code
                )
            
            minimal_results.append(ComplaintListOptimized(
                id=obj.id,
                user_type=obj.user_type,
                status=obj.status,
                complaint_date=obj.complaint_date,
                code=obj.code,
                vendor=vendor_data,
                customer=customer_data,
                is_active=obj.is_active,
                created_at=obj.created_at,
                updated_at=obj.updated_at,
                updated_by=obj.updated_by
            ))
        
        return ComplaintListDashboard(results=minimal_results, statistics=statistics)

    async def list_all(
        self,
        request: Request,
        search: str | None = None,
        user_type: Optional[UserTypeEnum] = None,
        status: Optional[ComplaintStatusEnum] = None,
        subject_type: Optional[SubjectTypeEnum] = None,
        vendor_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        time_period: Optional[TimePeriodEnum] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        statement = select(Model).options(
            # Customer block
            joinedload(Model.customer)
                .load_only(
                    Customer.customer_name,
                    Customer.customer_code,
                    Customer.pin_code,
                    Customer.location,
                    Customer.country_id,
                    Customer.state_id,
                    Customer.district_id,
                    Customer.city_id,
                ),
            joinedload(Model.customer).joinedload(Customer.country).load_only(Country.name),
            joinedload(Model.customer).joinedload(Customer.state).load_only(State.name),
            joinedload(Model.customer).joinedload(Customer.district).load_only(District.name),
            joinedload(Model.customer).joinedload(Customer.city).load_only(City.name),

            # Vendor block
            joinedload(Model.vendor)
                .load_only(
                    Vendor.vendor_name,
                    Vendor.vendor_code,
                    Vendor.pin_code,
                    Vendor.location,
                    Vendor.country_id,
                    Vendor.state_id,
                    Vendor.district_id,
                    Vendor.city_id,
                ),
            joinedload(Model.vendor).joinedload(Vendor.country).load_only(Country.name),
            joinedload(Model.vendor).joinedload(Vendor.state).load_only(State.name),
            joinedload(Model.vendor).joinedload(Vendor.district).load_only(District.name),
            joinedload(Model.vendor).joinedload(Vendor.city).load_only(City.name),
        )

        # Create a separate statement for statistics that only includes scope filters
        stats_statement = select(Model)

        user = request.state.user
        if user and user.role:
            role_name = user.role.name.lower()
            
            if role_name == "customer":
                customer_stmt = select(Customer).where(Customer.user_id == user.id)
                cust_result = await self.session.execute(customer_stmt)
                customer = cust_result.unique().scalar_one_or_none()
                if customer:
                    statement = statement.where(Model.customer_id == customer.id)
                    stats_statement = stats_statement.where(Model.customer_id == customer.id)
            elif role_name == "vendor":
                vendor_stmt = select(Vendor).where(Vendor.user_id == user.id)
                vend_result = await self.session.execute(vendor_stmt)
                vendor = vend_result.unique().scalar_one_or_none()
                if vendor:
                    statement = statement.where(Model.vendor_id == vendor.id)
                    stats_statement = stats_statement.where(Model.vendor_id == vendor.id)
        if search:
            statement = statement.where(
                or_(
                    Model.vendor.has(Vendor.vendor_name.ilike(f"%{search}%")),
                    Model.customer.has(Customer.customer_name.ilike(f"%{search}%"))
                )
            )
        if user_type:
            statement = statement.where(Model.user_type == user_type)
        if status:
            statement = statement.where(Model.status == status)
        if subject_type:
            statement = statement.where(Model.subject_type == subject_type)
        if vendor_id:
            statement = statement.where(Model.vendor_id == vendor_id)
        if customer_id:
            statement = statement.where(Model.customer_id == customer_id)

        # Date range
        date_start, date_end = get_date_range(time_period, start_date, end_date)
        if date_start:
            statement = statement.where(Model.created_at >= date_start)
        if date_end:
            statement = statement.where(Model.created_at <= date_end)

        # Calculate statistics
        statistics = await self._get_statistics(stats_statement)

        # Execute query and get all results
        statement = statement.order_by(Model.created_at.desc())
        result = await self.session.execute(statement)
        results = result.unique().scalars().all()



        # Return all entries with statistics (no pagination)
        return ListSchema(
            total=len(results),
            statistics=statistics,
            results=[await self._to_read_schema(obj) for obj in results]
        )


    async def read(self, id: UUID) -> ComplaintDetailRead:
        """Get single complaint by ID with timeline"""
        obj = await self.get_object(id, load_history=True)  
        return await self._to_detail_schema(obj)

    async def _validate_user_reference(self, item: CreateSchema) -> None:
        """Validate vendor or customer exists (DRY principle)"""
        if item.user_type == UserTypeEnum.VENDOR:
            if not item.vendor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="vendor_id is required when user_type is Vendor"
                )
            vendor = await self.session.get(Vendor, item.vendor_id)
            if not vendor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Vendor with id {item.vendor_id} not found"
                )

        elif item.user_type == UserTypeEnum.CUSTOMER:
            if not item.customer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="customer_id is required when user_type is Customer"
                )
            customer = await self.session.get(Customer, item.customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer with id {item.customer_id} not found"
                )

    def _create_status_history(self, complaint_id: UUID, status: ComplaintStatusEnum, user_id: UUID, remarks: str = None) -> None:
        """Create status history entry (DRY principle)"""
        history = ComplaintStatusHistory(
            complaint_id=complaint_id,
            status=status,
            changed_at=datetime.utcnow(),
            changed_by=user_id,
            remarks=remarks
        )
        self.session.add(history)

    async def create(self, request: Request, item: CreateSchema) -> ComplaintDetailRead:
        """Create new complaint"""
        try:
            user = request.state.user
            await self._validate_user_reference(item)
            
            # Create the complaint object
            obj = Model(
                **item.dict(),
                created_by=user.id,
                updated_by=user.id
            )
            self.session.add(obj)
            await self.session.flush()
            
            # Generate code
            last_complaint_stmt = select(Model).where(Model.code.isnot(None)).order_by(Model.code.desc()).limit(1)
            last_result = await self.session.execute(last_complaint_stmt)
            last_complaint = last_result.unique().scalar_one_or_none()
            
            counter = 1
            if last_complaint and last_complaint.code:
                try:
                    counter = int(last_complaint.code.replace('CMP', '')) + 1
                except (ValueError, AttributeError):
                    count_stmt = select(func.count()).select_from(Model)
                    count_result = await self.session.execute(count_stmt)
                    counter = count_result.scalar() + 1
            
            obj.code = f"CMP{counter:06d}"
            
            # ✅ Create initial OPEN status history
            self._create_status_history(
                complaint_id=obj.id,
                status=ComplaintStatusEnum.OPEN,
                user_id=user.id,
                remarks="Complaint created"
            )
            
            await self.session.commit()
            
            # Reload with history
            obj = await self.get_object(obj.id, load_history=True)
            
            return await self._to_detail_schema(obj)
            
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )



    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> ComplaintDetailRead:
        """Update existing complaint"""
        try:
            user = request.state.user
            obj = await self.get_object(id, load_history=True)

            # Update fields
            for key, value in item.dict(exclude_unset=True).items():
                setattr(obj, key, value)

            obj.updated_by = user.id
            obj.updated_at = datetime.utcnow()

            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            
            return await self._to_detail_schema(obj)

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def _handle_user_deactivation(self, complaint: Model, has_note: bool) -> None:
        """
        Handle user deactivation based on complaint closure.
        
        Rules:
        - If status = CLOSED with note: Do NOT deactivate user
        - If status = CLOSED without note: Deactivate user (set is_active = False)
        - Only applies when subject_type = BLOCK
        """
        if complaint.subject_type != SubjectTypeEnum.BLOCK:
            return
        
        if has_note:
            return  # Note provided, do NOT deactivate
        
        # No note provided, deactivate the user
        if complaint.user_type == UserTypeEnum.VENDOR and complaint.vendor_id:
            stmt = select(Vendor).options(selectinload(Vendor.user)).where(Vendor.id == complaint.vendor_id)
            result = await self.session.execute(stmt)
            vendor = result.scalar_one_or_none()
            
            if vendor:
                vendor.is_active = False
                if vendor.user:
                    vendor.user.is_active = False
            
                self.session.add(vendor)
        
        elif complaint.user_type == UserTypeEnum.CUSTOMER and complaint.customer_id:
            stmt = select(Customer).options(selectinload(Customer.user)).where(Customer.id == complaint.customer_id)
            result = await self.session.execute(stmt)
            customer = result.scalar_one_or_none()
            
            if customer:
                customer.is_active = False
                if customer.user:
                    customer.user.is_active = False
            
                self.session.add(customer)

    async def update_status(
        self, 
        request: Request, 
        id: UUID, 
        status_update: StatusUpdateSchema
    ) -> ComplaintDetailRead:
        """Update complaint status and track in timeline"""
        try:
            user = request.state.user
            complaint = await self.get_object(id, load_history=True)
            
           
            complaint.status_note = status_update.note
            
          
            self._create_status_history(
                complaint_id=complaint.id,
                status=status_update.status,
                user_id=user.id,
                remarks=status_update.note
            )
            
        
            complaint.status = status_update.status
            complaint.updated_by = user.id
            complaint.updated_at = datetime.utcnow()
            
          
            if status_update.status == ComplaintStatusEnum.CLOSED:
                has_note = bool(status_update.note and status_update.note.strip())
                await self._handle_user_deactivation(complaint, has_note)
            
            self.session.add(complaint)
            await self.session.commit()
            await self.session.refresh(complaint)
            
            return await self._to_detail_schema(complaint)

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def delete(self, request: Request, id: UUID):
        """Delete complaint"""
        try:
            obj = await self.get_object(id)
            await self.session.delete(obj)
            await self.session.commit()
            return {"detail": OBJECT_DELETED}
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )
