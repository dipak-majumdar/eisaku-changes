import json
import os
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, Request, UploadFile
from sqlalchemy.orm import selectinload, joinedload, raiseload
from sqlalchemy import select, or_, func
from typing import Optional, List

from models.advance_payment import AdvancePayment
from models.enums import TimePeriodEnum
from models.role import Role
from models.trip import (
    Trip as Model,
    TripAddress,
    TripStatusEnum, AddressTypeEnum,
    TripStatusHistory,
    TripVendor,
    TripDriver,
    TripDocument,
)
from models import Branch, Customer, VehicleType, Country, State, District, City, Employee, Vendor
from models.user import User
from schemas.trip import ( 
    IdNameCode,
    TripList as ListSchema,
    TripRead as ReadSchema,
    TripCreate as CreateSchema,
    TripUpdate as UpdateSchema,
    TripStatistics,
    TripStatusUpdate,
    AddressCreate,
    StatusHistoryRead,
    AddressRead,
    TripVendorAssign,
    TripVendorRead,
    TripDriverRead,
    TripDriverCreate,
    VehicleLoadingDocumentRead,
    VendorWithAddress,
    TripMinimal,
    TripMinimalList,
    MinimalAddressLoad,
)
from schemas.branch import IdName
from services.mail import send_email
from utils.date_helpers import get_date_range
from services.notification_helpers import NotificationHelper
from services.helper import get_supervisors_in_branch, get_branch_manager_id, administrative_user_id

RATE_DIFF = float(os.environ.get("RATE_DIFF", "5"))  

OBJECT_NOT_FOUND = "Trip not found"
OBJECT_DELETED = "Trip deleted successfully"
TRIP_RATE = "Trip Rate"
LOADING_UNLOADING_CHARGES = "Loading & Unloading Charges"

def save_upload_file(upload_file: UploadFile, upload_dir: str) -> str:
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{upload_file.filename}"
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload_file.file.read())
    return file_path.replace('\\', '/')


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    # async def _get_user_branch_id(self, user_id: UUID) -> UUID:
    #     """Get branch_id for a user through employee relationship"""
    #     stmt = (
    #         select(Employee)
    #         .options(joinedload(Employee.branch))
    #         .filter(Employee.user_id == user_id)
    #         .filter(Employee.is_active == True)
    #     )
    #     result = await self.session.execute(stmt)
    #     employee = result.scalars().first()
        
    #     if not employee:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="User must be associated with an employee record"
    #         )
        
    #     if not employee.branch_id:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail="User must be associated with a branch"
    #         )
        
    #     return employee.branch_id

    async def _get_user_branch_and_manager(self, user_id: UUID) -> tuple[UUID, Optional[UUID]]:
        """Get branch_id and manager_id for a user through employee relationship"""
        stmt = (
            select(Employee)
            .options(joinedload(Employee.branch))
            .filter(Employee.user_id == user_id)
            .filter(Employee.is_active == True)
        )
        result = await self.session.execute(stmt)
        employee = result.scalars().first()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be active and associated with an employee record"
            )
        
        if not employee.branch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be associated with a branch"
            )
        
        # Get branch manager for this branch
        manager_stmt = (
            select(Employee)
            .join(User, Employee.user_id == User.id)
            .join(Role, User.role_id == Role.id)
            .filter(
                Employee.branch_id == employee.branch_id,
                Role.name == "branch manager"
            )
        )
        manager_result = await self.session.execute(manager_stmt)
        branch_manager = manager_result.scalars().first()
        manager_id = branch_manager.user_id if branch_manager else None
        
        return employee.branch_id, manager_id

    async def _generate_trip_code(self) -> str:
        """Generate unique trip code"""
        stmt = (
            select(Model)
            .filter(Model.trip_code.isnot(None))
            .order_by(Model.trip_code.desc())
        )
        result = await self.session.execute(stmt)
        last_trip = result.scalars().first()
        
        counter = 1
        if last_trip and last_trip.trip_code:
            try:
                counter = int(last_trip.trip_code.replace('TRP', '')) + 1
            except (ValueError, AttributeError):
                count_stmt = select(Model)
                count_result = await self.session.execute(count_stmt)
                counter = len(count_result.scalars().all()) + 1
        
        return f"TRP{counter:06d}"

    def _create_payment_placeholder(
        self,
        trip: Model,
        vendor_id: UUID,
        user_id: UUID,
        amount: Decimal,
        payment_type: str,
        is_deduct_amount: bool = False,
    ):
        """Creates a placeholder record in the AdvancePayment table."""
        self.session.add(
            AdvancePayment(
                trip_id=trip.id,
                vendor_id=vendor_id,
                payment_date=date.today(),
                amount=amount,
                payment_type=payment_type,
                is_paid_amount=False,
                is_deduct_amount=is_deduct_amount,
                created_by=user_id,
                updated_by=user_id,
            )
        )


    async def get_object(self, id: UUID) -> Model:
        """Get trip with all relationships"""
        stmt = (
            select(Model)
            .options(
                joinedload(Model.branch),
                joinedload(Model.customer),
                joinedload(Model.vehicle_type),
                selectinload(Model.addresses).joinedload(TripAddress.country),
                selectinload(Model.addresses).joinedload(TripAddress.state),
                selectinload(Model.addresses).joinedload(TripAddress.district),
                selectinload(Model.addresses).joinedload(TripAddress.city),
                selectinload(Model.status_history).joinedload(TripStatusHistory.changed_by_user),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.vendor),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.vehicle_type),
                selectinload(Model.assigned_vendor).selectinload(TripVendor.drivers),
                selectinload(Model.trip_documents),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.branch),
            )
            .filter(Model.id == id)
        )
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=OBJECT_NOT_FOUND
            )
        return obj

    def _parse_addresses_json(self, addresses_json: str) -> List[AddressCreate]:
        """Parse JSON string to list of AddressCreate objects"""
        try:
            addresses_data = json.loads(addresses_json)
            if not isinstance(addresses_data, list):
                raise ValueError("Addresses must be a JSON array")
            
            addresses = []
            for addr_data in addresses_data:
                addresses.append(AddressCreate(**addr_data))
            
            if len(addresses) == 0:
                raise ValueError("At least one address is required")
            
            return addresses
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format for addresses"
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    def _to_read_schema(self, obj: Model, request: Request) -> ReadSchema:
        """Convert Trip model to read schema"""
        loading_addresses = []
        unloading_addresses = []

        for addr in sorted(obj.addresses, key=lambda x: (x.address_type, x.sequence)):
            address_read = AddressRead(
                    id=addr.id,
                    address_type=addr.address_type,
                    country=IdName(id=addr.country.id, name=addr.country.name),
                    state=IdName(id=addr.state.id, name=addr.state.name),
                    district=IdName(id=addr.district.id, name=addr.district.name),
                    city=IdName(id=addr.city.id, name=addr.city.name),
                    location=addr.location,
                    pincode=addr.pincode
                )
            if addr.address_type == AddressTypeEnum.LOADING:
                loading_addresses.append(address_read)
            elif addr.address_type == AddressTypeEnum.UNLOADING:
                unloading_addresses.append(address_read)
        
        status_history = []
        if obj.status_history:
            for history in obj.status_history:
                updated_by_id = None
                if history.changed_by_user and hasattr(history.changed_by_user, 'id'):
                    updated_by_id = history.changed_by_user.id

                status_history.append(StatusHistoryRead(
                    previous_status=history.previous_status,
                    current_status=history.current_status,
                    updated_at=history.created_at,
                    updated_by=updated_by_id,
                    remarks=history.remarks
                ))

        assigned_vendor_read = None
        if obj.assigned_vendor:
            tv = obj.assigned_vendor
            assigned_vendor_read = TripVendorRead(
                id=tv.id,
                vendor=VendorWithAddress(id=tv.vendor.id, name=tv.vendor.vendor_name,address=tv.vendor.address, code=tv.vendor.vendor_code, type=tv.vendor.vendor_type.value),
                vehicle_type=IdName(id=tv.vehicle_type.id, name=tv.vehicle_type.name),
                tons=tv.tons,
                vehicle_no=tv.vehicle_no,
                insurance_expiry_date=tv.insurance_expiry_date,
                rc_copy=tv.rc_copy,
                insurance_copy=tv.insurance_copy,
                trip_rate=tv.trip_rate, 
                advance=tv.advance, 
                other_charges=tv.other_charges,
                other_unloading_charges=tv.other_unloading_charges,
                balance=tv.balance,
                drivers=[TripDriverRead.model_validate(driver) for driver in tv.drivers],
            )

        # Determine which role can approve the trip rate
        trip_rate_can_approve_role = None
        if obj.assigned_vendor:
            customer_rate = obj.trip_rate
            vendor_rate = obj.assigned_vendor.trip_rate
            
            if customer_rate > 0:
                perc_diff = abs(customer_rate - vendor_rate) / customer_rate * 100
            else:
                perc_diff = 0
            
            if perc_diff > RATE_DIFF:
                trip_rate_can_approve_role = "branch manager"
            else:
                trip_rate_can_approve_role = "management"

        can_view_fleet_rate = True
        user = request.state.user
        if user.role.name.lower() in ['supplier lead', 'vendor']:
            can_view_fleet_rate = False

        trip_rate = 0
        loading_unloading_charges = 0

        if user.role.name.lower() not in ['vendor']:
            trip_rate = obj.trip_rate
            loading_unloading_charges = obj.loading_unloading_charges

        return ReadSchema(
            id=obj.id,
            trip_code=obj.trip_code,
            trip_date=obj.trip_date,
            status=obj.status,
            capacity=obj.capacity,
            goods_type=obj.goods_type,
            goods_name=obj.goods_name,
            is_shortage=obj.is_shortage,
            is_damage=obj.is_damage,
            deducted_amount=obj.deducted_amount,
            deducted_details=obj.deducted_details,
            advance_approval=obj.is_advance_payment_done,
            balance_approval=obj.is_balance_payment_approve,
            trip_rate=trip_rate,
            loading_unloading_charges=loading_unloading_charges,
            late_fine=obj.pod_penalty_amount,
            instructions=obj.instructions,
            can_approve_role=trip_rate_can_approve_role,
            pod_sent_to_customer=obj.pod_sent_to_customer,
            cancellation_reason=obj.cancellation_reason,
            can_view_fleet_rate=can_view_fleet_rate,
            branch={
                "id": obj.branch.id,
                "name": obj.branch.name,
                "code": obj.branch.code,
                "address": obj.branch.address,
            },
            customer={
                "id": obj.customer.id,
                "name": obj.customer.customer_name,
                "code": obj.customer.customer_code,
                "type": obj.customer.customer_type.value,
                "address": obj.customer.address,
                
            },
            vehicle_type=IdName(id=obj.vehicle_type.id, name=obj.vehicle_type.name),
            loading_addresses=loading_addresses,
            unloading_addresses=unloading_addresses,
            status_history=status_history,
            assigned_vendor=assigned_vendor_read,
            vehicle_loading_unloading_documents=VehicleLoadingDocumentRead.model_validate(obj.trip_documents) if obj.trip_documents else None,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            created_by=obj.created_by,
            updated_by=obj.updated_by,
        )

    async def _calculate_statistics(self, query) -> TripStatistics:
        """Calculate trip statistics"""
        from sqlalchemy import func, case
        
        # Add eager loading for status_history to avoid MissingGreenlet error
        query_with_history = query.options(selectinload(Model.status_history))
        
        # Execute the query with status_history loaded
        result = await self.session.execute(query_with_history)
        all_trips = result.scalars().all()
        
        # Count total
        total = len(all_trips)
        
        
        pending = sum(1 for trip in all_trips if trip.status == TripStatusEnum.PENDING)
        
        # In Transit: Trips that are VEHICLE_LOADED but not yet VEHICLE_UNLOADED
        # Check status_history to see if VEHICLE_UNLOADED has been reached
        in_progress = 0
        for trip in all_trips:
            if trip.status == TripStatusEnum.VEHICLE_LOADED:
                # Check if trip has reached VEHICLE_UNLOADED status in history
                has_unloaded = False
                if trip.status_history:
                    has_unloaded = any(
                        h.current_status == TripStatusEnum.VEHICLE_UNLOADED 
                        for h in trip.status_history
                    )
                # Count as in_progress if loaded but not unloaded
                if not has_unloaded:
                    in_progress += 1
        
        completed = sum(1 for trip in all_trips if trip.status == TripStatusEnum.COMPLETED)
        rejected = sum(1 for trip in all_trips if trip.status == TripStatusEnum.REJECTED)
        
        return TripStatistics(
            total=total,
            pending=pending,
            in_progress=in_progress,
            completed=completed,
            rejected=rejected
        )

    async def _paginate(self, base_query, request: Request, page=1, size=10) -> ListSchema:
        """Paginate query results"""
        # Get statistics
        statistics = await self._calculate_statistics(base_query)
        
        # Get total count
        count_result = await self.session.execute(base_query)
        total = len(count_result.scalars().all())
        
        offset = (page - 1) * size
        
        # Get paginated results with all relationships
        stmt = (
            base_query
            .options(
                joinedload(Model.branch),
                joinedload(Model.customer),
                joinedload(Model.vehicle_type),
                selectinload(Model.addresses).joinedload(TripAddress.country),
                selectinload(Model.addresses).joinedload(TripAddress.state),
                selectinload(Model.addresses).joinedload(TripAddress.district),
                selectinload(Model.addresses).joinedload(TripAddress.city),
                selectinload(Model.status_history).joinedload(TripStatusHistory.changed_by_user),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.vendor),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.vehicle_type),
                selectinload(Model.assigned_vendor).selectinload(TripVendor.drivers),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.branch),
                selectinload(Model.trip_documents),  # ✅ ADD THIS LINE
            )
            .order_by(Model.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        
        result = await self.session.execute(stmt)
        results = result.scalars().unique().all()

        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )

        converted_results = [self._to_read_schema(obj, request) for obj in results]
        return ListSchema(
            total=total,
            statistics=statistics,
            next=next_url,
            previous=previous_url,
            results=converted_results
        )

    async def list(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        branch_id: Optional[UUID] = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        trip_status: Optional[TripStatusEnum] = None,
    ) -> ListSchema:
        """List trips with filters"""
        user = request.state.user
        
        query = select(Model)

        # Handle vendor role
        if user.role.name.lower() == "vendor":
            stmt = select(Vendor).filter(Vendor.user_id == user.id)
            result = await self.session.execute(stmt)
            vendor_record = result.scalars().first()
            
            if vendor_record:
                query = query.join(TripVendor).filter(TripVendor.vendor_id == vendor_record.id)
            else:
                return ListSchema(
                    total=0, 
                    statistics=TripStatistics(total=0, pending=0, in_progress=0, completed=0, rejected=0), 
                    results=[]
                )
        
        # Handle customer role
        elif user.role.name.lower() == "customer":
            stmt = select(Customer).filter(Customer.user_id == user.id)
            result = await self.session.execute(stmt)
            customer_record = result.scalars().first()
            
            if customer_record:
                query = query.filter(Model.customer_id == customer_record.id)
            else:
                return ListSchema(
                    total=0, 
                    statistics=TripStatistics(total=0, pending=0, in_progress=0, completed=0, rejected=0), 
                    results=[]
                )
        
        # For all other users, check if they have branch_id in employee table
        else:
            stmt = (
                select(Employee)
                .filter(Employee.user_id == user.id)
                .filter(Employee.is_active == True)
            )
            result = await self.session.execute(stmt)
            employee = result.scalars().first()
            print('checked--------------------------------------------------------')
            
            # If employee record exists and has branch_id, filter by branch
            if employee and employee.branch_id:
                query = query.filter(Model.branch_id == employee.branch_id)
                print('checked+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            # If no employee record or no branch_id, user can see all trips (admin/superuser)

        if customer_id:
            query = query.filter(Model.customer_id == customer_id)
        
        if branch_id:
            query = query.filter(Model.branch_id == branch_id)
        
        if trip_status:
            query = query.filter(Model.status == trip_status)
        
        if search:
            query = query.filter(
                or_(
                    Model.trip_code.ilike(f"%{search}%"),
                    Model.customer.has(Customer.customer_name.ilike(f"%{search}%")),
                    Model.assigned_vendor.has(TripVendor.vendor.has(Vendor.vendor_name.ilike(f"%{search}%")))
                )
            )

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            query = query.where(Model.created_at >= start_date, Model.created_at <= end_date)

        return await self._paginate(query, request, page, size)

    async def list_minimal(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        branch_id: Optional[UUID] = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        trip_status: Optional[TripStatusEnum] = None,
    ) -> TripMinimalList:
        """Optimized minimal trip listing with essential data only"""
        user = request.state.user
        
        query = select(Model)

        # Handle vendor role
        if user.role.name.lower() == "vendor":
            stmt = select(Vendor).filter(Vendor.user_id == user.id)
            result = await self.session.execute(stmt)
            vendor_record = result.scalars().first()
            
            if vendor_record:
                query = query.join(TripVendor).filter(TripVendor.vendor_id == vendor_record.id)
            else:
                return TripMinimalList(total=0, results=[])
        
        # Handle customer role
        elif user.role.name.lower() == "customer":
            stmt = select(Customer).filter(Customer.user_id == user.id)
            result = await self.session.execute(stmt)
            customer_record = result.scalars().first()
            
            if customer_record:
                query = query.filter(Model.customer_id == customer_record.id)
            else:
                return TripMinimalList(total=0, results=[])
        
        # For all other users, check if they have branch_id in employee table
        else:
            stmt = (
                select(Employee)
                .filter(Employee.user_id == user.id)
                .filter(Employee.is_active == True)
            )
            result = await self.session.execute(stmt)
            employee = result.scalars().first()
            
            # If employee record exists and has branch_id, filter by branch
            if employee and employee.branch_id:
                query = query.filter(Model.branch_id == employee.branch_id)

        if customer_id:
            query = query.filter(Model.customer_id == customer_id)
        
        if branch_id:
            query = query.filter(Model.branch_id == branch_id)
        
        if trip_status:
            query = query.filter(Model.status == trip_status)
        
        if search:
            query = query.filter(
                or_(
                    Model.trip_code.ilike(f"%{search}%"),
                    Model.customer.has(Customer.customer_name.ilike(f"%{search}%")),
                )
            )

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            query = query.where(Model.created_at >= start_date, Model.created_at <= end_date)

        # Optimized count statement
        count_statement = select(func.count()).select_from(query.with_only_columns(Model.id).subquery())

        # Load only essential relationships for minimal data
        statement = query.options(
            selectinload(Model.customer),
            selectinload(Model.addresses).options(
                selectinload(TripAddress.country),
                selectinload(TripAddress.state),
                selectinload(TripAddress.district),
                selectinload(TripAddress.city),
            ),
            raiseload('*')
        ).order_by(Model.created_at.desc())
        
        return await self._paginate_minimal(statement, request, page, size, count_statement=count_statement)

    def _to_minimal_schema(self, obj: Model) -> TripMinimal:
        """Convert Trip model to TripMinimal for fast listing"""
        
        # Separate loading and unloading addresses - oldest loading, newest unloading
        loading_addresses = []
        unloading_addresses = []
        
        # Get loading addresses (oldest first) and unloading addresses (newest first)
        loading_addrs = [addr for addr in obj.addresses if addr.address_type == AddressTypeEnum.LOADING]
        unloading_addrs = [addr for addr in obj.addresses if addr.address_type == AddressTypeEnum.UNLOADING]
        
        # Sort loading addresses by created_at ascending (oldest first)
        if loading_addrs:
            oldest_loading = sorted(loading_addrs, key=lambda addr: addr.created_at)[0]
            loading_addresses.append(MinimalAddressLoad(
                address_type=oldest_loading.address_type,
                country=oldest_loading.country.name if oldest_loading.country else "",
                state=oldest_loading.state.name if oldest_loading.state else "",
                district=oldest_loading.district.name if oldest_loading.district else "",
                city=oldest_loading.city.name if oldest_loading.city else "",
                location=oldest_loading.location,
                pincode=oldest_loading.pincode
            ))
        
        # Sort unloading addresses by created_at descending (newest first)
        if unloading_addrs:
            newest_unloading = sorted(unloading_addrs, key=lambda addr: addr.created_at, reverse=True)[0]
            unloading_addresses.append(MinimalAddressLoad(
                address_type=newest_unloading.address_type,
                country=newest_unloading.country.name if newest_unloading.country else "",
                state=newest_unloading.state.name if newest_unloading.state else "",
                district=newest_unloading.district.name if newest_unloading.district else "",
                city=newest_unloading.city.name if newest_unloading.city else "",
                location=newest_unloading.location,
                pincode=newest_unloading.pincode
            ))
        
        # Convert Customer model to IdNameCode format
        customer_obj = None
        if obj.customer:
            customer_obj = IdNameCode(
                id=obj.customer.id,
                name=obj.customer.customer_name,
                code=obj.customer.customer_code,
                type="customer"
            )
        
        return TripMinimal(
            id=obj.id,
            customer=customer_obj,
            trip_code=obj.trip_code,
            trip_date=obj.trip_date,
            status=obj.status,
            loading_addresses=loading_addresses,
            unloading_addresses=unloading_addresses,
        )

    async def _paginate_minimal(self, statement, request: Request, page=1, size=10, count_statement=None) -> TripMinimalList:
        """Paginate with optimized query for minimal listing"""
        # Get statistics first (using the same query)
        statistics = await self._calculate_statistics(statement)
        
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
        return TripMinimalList(total=total, statistics=statistics, next=next_url, previous=previous_url, results=minimal_results)

    async def list_by_trip_date_priority(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        trip_status: Optional[TripStatusEnum] = None,
    ) -> ListSchema:
        """
        List trips ordered by:
        1. Today's trips (trip_date == current_date)
        2. Future trips (trip_date > current_date)
        3. Past trips (trip_date < current_date)
        """
        from sqlalchemy import case
        
        query = select(Model)

        if customer_id:
            query = query.filter(Model.customer_id == customer_id)
        
        if trip_status:
            query = query.filter(Model.status == trip_status)
        
        if search:
            query = query.filter(Model.trip_code.ilike(f"%{search}%"))

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            query = query.where(Model.created_at >= start_date, Model.created_at <= end_date)

        today = date.today()
        query = query.order_by(
            case(
                (Model.trip_date == today, 1),
                (Model.trip_date > today, 2),
                (Model.trip_date < today, 3),
            ),
            Model.trip_date.desc(),
            Model.created_at.desc()
        )

        return await self._paginate(query, request, page, size)

    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Get single trip"""
        obj = await self.get_object(id)
        return self._to_read_schema(obj, request)

    async def create(self, request: Request, item: CreateSchema) -> ReadSchema:
        """Create new trip"""
        try:
            user = request.state.user
            branch_id, manager_id = await self._get_user_branch_and_manager(user.id)
            
            loading_addresses = item.loading_addresses
            unloading_addresses = item.unloading_addresses
            
            trip_code = await self._generate_trip_code()
            
            if not loading_addresses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one loading address is required.")
            if not unloading_addresses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one unloading address is required.")

            trip = Model(
                trip_code=trip_code,
                branch_id=branch_id,
                trip_date=item.trip_date,
                customer_id=item.customer_id,
                vehicle_type_id=item.vehicle_type_id,
                capacity=item.capacity,
                goods_type=item.goods_type,
                goods_name=item.goods_name,
                trip_rate=item.trip_rate,
                loading_unloading_charges=item.loading_unloading_charges,
                instructions=item.instructions,                
                created_by=user.id,
                updated_by=user.id
            )
            
            self.session.add(trip)
            await self.session.flush()
            
            initial_history = TripStatusHistory(
                trip_id=trip.id,
                previous_status=None,
                current_status=TripStatusEnum.PENDING,
                remarks="Trip created",
                updated_by=user.id
            )
            self.session.add(initial_history)

            # Add loading addresses
            for idx, addr_data in enumerate(loading_addresses, start=1):
                state = await self.session.get(State, addr_data.state_id)
                if not state:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"State with ID {addr_data.state_id} not found for loading address."
                    )

                address = TripAddress(
                    trip_id=trip.id,
                    address_type=AddressTypeEnum.LOADING,
                    country_id=state.country_id,
                    state_id=addr_data.state_id,
                    district_id=addr_data.district_id,
                    city_id=addr_data.city_id,
                    location=addr_data.location,
                    pincode=addr_data.pincode,
                    sequence=idx,
                    created_by=user.id,
                    updated_by=user.id
                )
                self.session.add(address)
            
            # Add unloading addresses
            for idx, addr_data in enumerate(unloading_addresses, start=1):
                state = await self.session.get(State, addr_data.state_id)
                if not state:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"State with ID {addr_data.state_id} not found for unloading address."
                    )

                address = TripAddress(
                    trip_id=trip.id,
                    address_type=AddressTypeEnum.UNLOADING,
                    country_id=state.country_id,
                    state_id=addr_data.state_id,
                    district_id=addr_data.district_id,
                    city_id=addr_data.city_id,
                    location=addr_data.location,
                    pincode=addr_data.pincode,
                    sequence=idx,
                    created_by=user.id,
                    updated_by=user.id
                )
                self.session.add(address)
            
            await self.session.commit()
            
            
            # ✅ Send targeted notification to branch manager (non-blocking)
            try:
                from core.websocket_manager import socket_manager
                
                if manager_id:
                    notification_data = {
                        "notification_type": "trip_created",
                        "message": f"New trip {trip.trip_code} created - approval required",
                        "trip_id": str(trip.id),
                        "trip_code": trip.trip_code,
                        "trip_date": str(trip.trip_date),
                        "customer_id": str(trip.customer_id),
                        "action_required": True,
                        "action_data": {
                            "trip_id": str(trip.id),
                            "trip_code": trip.trip_code
                        },
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    # Send to specific branch manager only
                    await socket_manager.send_to_users(
                        user_ids=[str(manager_id)],
                        notification=notification_data,
                        db_session=None  # Notification service handles DB save
                    )
                    print(f"✅ Trip creation notification sent to branch manager: {manager_id}")
                else:
                    print(f"⚠️ No branch manager found for notification")
            except Exception as notification_error:
                # Log notification error but don't fail the trip creation
                print(f"❌ Failed to send trip creation notification: {str(notification_error)}")
            
            # FIX: Reload trip with customer relationship eagerly loaded
            # ✅ FIX: Reload trip with customer relationship eagerly loaded
            stmt = (
                select(Model)
                .options(
                    joinedload(Model.customer).joinedload(Customer.user)
                )
                .filter(Model.id == trip.id)
            )
            result = await self.session.execute(stmt)
            trip = result.scalars().first()

            # ✅ FIX: Get customer separately with user relationship
            stmt_customer = (
                select(Customer)
                .options(joinedload(Customer.user))
                .filter(Customer.id == item.customer_id)
            )
            result_customer = await self.session.execute(stmt_customer)
            customer = result_customer.scalars().first()

            # Send mail to the customer
            if customer and customer.user and customer.user.email:
                
                if trip.trip_rate > 0:
                    customer_rate_create = AdvancePayment(
                        trip_id=trip.id,
                        customer_id=customer.id,
                        vendor_id=None,
                        payment_date=date.today(),
                        amount=trip.trip_rate,
                        payment_type=TRIP_RATE,
                        is_paid_amount=False,
                    )
                customer_loading_charges = None
                if trip.loading_unloading_charges > 0:
                    customer_loading_charges = AdvancePayment(
                        trip_id=trip.id,
                        customer_id=customer.id,
                        vendor_id=None,
                        payment_date=date.today(),
                        amount=trip.loading_unloading_charges,
                        payment_type=LOADING_UNLOADING_CHARGES,
                        is_paid_amount=False,
                    )
                self.session.add(customer_rate_create)
                if customer_loading_charges:
                    self.session.add(customer_loading_charges)
                await self.session.commit()


                header_msg = "New trip created"
                body_msg = f"A new trip has been created. Trip code: {trip.trip_code}"
                
                await send_email(
                    session=self.session,
                    request=request, 
                    user=customer.user, 
                    header_msg=header_msg, 
                    body_msg=body_msg
                )

            return await self.read(request, trip.id)

        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )


    async def assign_vendor(
        self,
        request: Request,
        id: UUID,
        item: TripVendorAssign,
        rc_copy: Optional[UploadFile] = None,
        insurance_copy: Optional[UploadFile] = None,
    ) -> ReadSchema:
        """Assign a vendor to a trip."""
        try:
            user = request.state.user
            trip = await self.get_object(id)

            if trip.assigned_vendor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A vendor is already assigned to this trip."
                )

            if trip.status not in [TripStatusEnum.APPROVED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Trip approval needed to assign a vendor."
                )

            # Check if related entities exist
            if not await self.session.get(Vendor, item.vendor_id):
                raise HTTPException(status_code=404, detail=f"Vendor with ID {item.vendor_id} not found.")
            if not await self.session.get(Branch, item.branch_id):
                raise HTTPException(status_code=404, detail=f"Branch with ID {item.branch_id} not found.")
            if not await self.session.get(VehicleType, item.vehicle_type_id):
                raise HTTPException(status_code=404, detail=f"Vehicle Type with ID {item.vehicle_type_id} not found.")

            vendor_data = item.model_dump(exclude={'drivers'})
            drivers_data = item.drivers

            upload_dir = "uploads/trip_documents"
            if rc_copy:
                vendor_data["rc_copy"] = save_upload_file(rc_copy, upload_dir)
            if insurance_copy:
                vendor_data["insurance_copy"] = save_upload_file(insurance_copy, upload_dir)

            trip_vendor = TripVendor(
                trip_id=id,
                **vendor_data,
                created_by=user.id,
                updated_by=user.id
            )
            self.session.add(trip_vendor)
            await self.session.flush()

            for driver_item in drivers_data:
                trip_driver = TripDriver(
                    trip_vendor_id=trip_vendor.id,
                    **driver_item.model_dump()
                )
                self.session.add(trip_driver)

            previous_status = trip.status
            trip.status = TripStatusEnum.VENDOR_ASSIGNED
            trip.updated_by = user.id
            trip.updated_at = datetime.utcnow()

            history_entry = TripStatusHistory(
                trip_id=trip.id,
                previous_status=previous_status,
                current_status=TripStatusEnum.VENDOR_ASSIGNED,
                remarks="Vendor Assigned",
                updated_by=user.id
            )
            self.session.add(history_entry)
            self.session.add(trip)

            self._create_payment_placeholder(trip, item.vendor_id, user.id, item.trip_rate, "Fleet rate")
            self._create_payment_placeholder(trip, item.vendor_id, user.id, item.other_charges, "Other Charges")

            await self.session.commit()
            
            # Send notification to branch manager when vendor is assigned
            try:
                # Get vendor details
                vendor = await self.session.get(Vendor, item.vendor_id)
                vendor_name = vendor.vendor_name if vendor else "Unknown Vendor"
                
                # Get branch manager for the trip's branch
                manager_id = await get_branch_manager_id(self.session, trip.branch_id)
                management_ids = await administrative_user_id(self.session, "management")
                
                if manager_id:
                    notification_helper = NotificationHelper(self.session)
                    await notification_helper.approve_flit_rate_notification(
                        user_ids=[manager_id, *management_ids],
                        trip_id=trip.id,
                        trip_code=trip.trip_code,
                        request=request
                    )
                    print(f"✅ Vendor assignment notification sent to branch manager: {manager_id}")
                else:
                    print(f"⚠️ No branch manager found for branch {trip.branch_id}")
            except Exception as notification_error:
                # Log notification error but don't fail the vendor assignment
                print(f"❌ Failed to send vendor assignment notification: {str(notification_error)}")
            
            self.session.expire(trip)
            updated_trip = await self.get_object(id)
            return self._to_read_schema(updated_trip, request)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    async def update_status(self, request: Request, id: UUID, item: TripStatusUpdate) -> ReadSchema:
        """Update trip status and create a history record."""
        try:
            user = request.state.user
            trip = await self.get_object(id)

            # Print all employee IDs from user's branch
            if hasattr(user, 'id') and user.id:

                user_employee_stmt = select(Employee).where(Employee.user_id == user.id)
                user_employee_result = await self.session.execute(user_employee_stmt)
                user_employee = user_employee_result.scalars().first()

                if not user_employee:
                    raise ValueError("Employee record not found for user")

                employees_result = await self.session.execute(
                    select(Employee).where(Employee.branch_id == user_employee.branch_id)
                )

                employees = employees_result.unique().scalars().all()

                branch_employee_ids = [str(emp.user_id) for emp in employees]


            
            # Store previous status before any changes
            previous_status = trip.status.value if trip.status else "Unknown"
            print(f"Previous status from database: {previous_status}")
            if trip.status == item.status:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The trip is already in the specified status."
                )

            if item.status == TripStatusEnum.PENDING:
                if trip.status != TripStatusEnum.REJECTED:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Trip can only be moved to 'Pending' from 'Rejected' status."
                    )
            
            if item.status in [TripStatusEnum.APPROVED, TripStatusEnum.REJECTED]:
                if trip.status != TripStatusEnum.PENDING:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Trip can only be approved or rejected if the current status is 'Pending'"
                    )
                
                role_name = getattr(getattr(user, 'role', None), 'name', '').lower()  
                if role_name != "branch manager":
                    raise HTTPException(
                        status_code=403,
                        detail="Only a Branch Manager can approve or reject trips."
                    )

                if item.remarks is None or item.remarks.strip() == "":
                    if item.status == TripStatusEnum.REJECTED:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Remarks are required when rejecting a trip."
                        )
            
            if item.status in [TripStatusEnum.FLEET_RATE_APPROVE, TripStatusEnum.FLEET_RATE_REJECT]:
                if trip.status != TripStatusEnum.VENDOR_ASSIGNED:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Trip rate can only be approved or rejected if the current status is 'Vendor Assigned'"
                    )

                if item.status in [TripStatusEnum.FLEET_RATE_APPROVE]:
                    customer_rate = trip.trip_rate              
                    vendor_obj = trip.assigned_vendor

                    if vendor_obj is None:
                        raise HTTPException(status_code=400, detail="No assigned vendor.")
                    vendor_rate = vendor_obj.trip_rate
                    
                    if customer_rate > 0:
                        perc_diff = abs(customer_rate - vendor_rate) / customer_rate * 100
                    else:
                        perc_diff = 0

                    role_name = getattr(getattr(user, 'role', None), 'name', '').lower()  

                    if perc_diff > RATE_DIFF:
                        if role_name != "branch manager":
                            raise HTTPException(
                                status_code=403,
                                detail=f"Only Branch Manager can approve when rate difference > {RATE_DIFF}%."
                            )
                    else:
                        if role_name != "management":
                            raise HTTPException(
                                status_code=403,
                                detail=f"Only Management can approve when rate difference <= {RATE_DIFF}%."
                            )

            history_entry = TripStatusHistory(
                trip_id=trip.id,
                previous_status=trip.status,
                current_status=item.status,
                remarks=item.remarks if item.remarks else item.status.value,
                updated_by=user.id
            )
            self.session.add(history_entry)

            trip.status = item.status
            if item.status == TripStatusEnum.REJECTED:
                trip.cancellation_reason = item.remarks
            
            trip.updated_by = user.id
            trip.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(trip)
            
            # Send notification to supervisors when trip is approved
            if item.status == TripStatusEnum.APPROVED:
                try:
                    supervisor_ids = await get_supervisors_in_branch(self.session, trip.branch_id)
                    
                    if supervisor_ids:
                        notification_helper = NotificationHelper(self.session)
                        await notification_helper.assign_vendor_notification(
                            user_ids=supervisor_ids,
                            trip_id=trip.id,
                            trip_code=trip.trip_code,
                            request=request
                        )
                        print(f"✅ Trip approval notification sent to {len(supervisor_ids)} supervisor(s)")
                    else:
                        print(f"⚠️ No supervisors found in branch {trip.branch_id}")
                except Exception as notification_error:
                    # Log notification error but don't fail the status update
                    print(f"❌ Failed to send supervisor notification: {str(notification_error)}")
            
            #send notifications to supervisor when flit rate is approved
            if item.status == TripStatusEnum.FLEET_RATE_APPROVE:
                try:
                    supervisor_ids = await get_supervisors_in_branch(self.session, trip.branch_id)
                    
                    if supervisor_ids:
                        notification_helper = NotificationHelper(self.session)
                        await notification_helper.flit_rate_approved_notification(
                            user_ids=supervisor_ids,
                            trip_id=trip.id,
                            trip_code=trip.trip_code,
                            request=request
                        )
                        print(f"✅ Trip approval notification sent to {len(supervisor_ids)} supervisor(s)")
                    else:
                        print(f"⚠️ No supervisors found in branch {trip.branch_id}")
                except Exception as notification_error:
                    # Log notification error but don't fail the status update
                    print(f"❌ Failed to send supervisor notification: {str(notification_error)}")
            

            # Send notification for status change
            notification_helper = NotificationHelper(self.session)
            await notification_helper.trip_status_changed(
                user_ids=branch_employee_ids,
                trip_id=trip.id,
                trip_code=trip.trip_code,
                previous_status=previous_status,
                new_status=item.status.value,
                request=request,
                remarks=item.remarks
            )
            
            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {str(e)}")

    async def read_vehicle_loading_documents(self, trip_id: UUID) -> VehicleLoadingDocumentRead:
        """Read vehicle loading documents for a specific trip."""
        trip = await self.get_object(trip_id)
        if not trip.trip_documents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No loading documents found for this trip."
            )
        
        return VehicleLoadingDocumentRead.model_validate(trip.trip_documents)

    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> ReadSchema:
        """Update trip"""
        try:
            user = request.state.user
            trip = await self.get_object(id)

            if trip.status != TripStatusEnum.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,    
                    details="Trip update possible when current status is 'Pending' only."
                )

            if item.customer_id != trip.customer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Customer cannot be changed after a trip is created."
                )
            
            loading_addresses = item.loading_addresses_json
            unloading_addresses = item.unloading_addresses_json

            trip.trip_date = item.trip_date
            trip.customer_id = item.customer_id
            trip.vehicle_type_id = item.vehicle_type_id
            trip.capacity = item.capacity
            trip.goods_type = item.goods_type
            trip.goods_name = item.goods_name
            trip.instructions = item.instructions
            trip.updated_by = user.id
            trip.updated_at = datetime.utcnow()
            
            # Update payment history if trip rate or loading/unloading charges changed
            from models.advance_payment import AdvancePayment
            from decimal import Decimal
            
            # Update customer payment records for trip rate change
            if trip.trip_rate != item.trip_rate:
                trip.trip_rate = item.trip_rate

                customer_payments_stmt = select(AdvancePayment).where(
                    AdvancePayment.trip_id == trip.id,
                    AdvancePayment.customer_id == trip.customer_id,
                    AdvancePayment.payment_type == TRIP_RATE
                )
                customer_payments_result = await self.session.execute(customer_payments_stmt)
                customer_payments = customer_payments_result.scalars().all()
                
                for payment in customer_payments:
                    payment.amount = item.trip_rate
                    payment.updated_by = user.id
                    payment.updated_at = datetime.utcnow()
                    self.session.add(payment)
            
            # Update customer payment records for loading/unloading charges change
            if trip.loading_unloading_charges != item.loading_unloading_charges:
                trip.loading_unloading_charges = item.loading_unloading_charges
                loading_payments_stmt = select(AdvancePayment).where(
                    AdvancePayment.trip_id == trip.id,
                    AdvancePayment.customer_id == trip.customer_id,
                    AdvancePayment.payment_type == LOADING_UNLOADING_CHARGES
                )
                loading_payments_result = await self.session.execute(loading_payments_stmt)
                loading_payments = loading_payments_result.scalars().all()
                
                for payment in loading_payments:
                    payment.amount = item.loading_unloading_charges or Decimal("0.0")
                    payment.updated_by = user.id
                    payment.updated_at = datetime.utcnow()
                    self.session.add(payment)
            
            existing_addresses_map = {str(addr.id): addr for addr in trip.addresses}
            incoming_address_ids = set()

            # Process loading addresses
            for idx, addr_data in enumerate(loading_addresses, start=1):
                state = await self.session.get(State, addr_data.state_id)
                if not state:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"State with ID {addr_data.state_id} not found.")

                if addr_data.id and str(addr_data.id) in existing_addresses_map:
                    address_to_update = existing_addresses_map[str(addr_data.id)]
                    address_to_update.country_id = state.country_id
                    address_to_update.state_id = addr_data.state_id
                    address_to_update.district_id = addr_data.district_id
                    address_to_update.city_id = addr_data.city_id
                    address_to_update.location = addr_data.location
                    address_to_update.pincode = addr_data.pincode
                    address_to_update.sequence = idx
                    address_to_update.address_type = AddressTypeEnum.LOADING
                    address_to_update.updated_by = user.id
                    address_to_update.updated_at = datetime.utcnow()
                    self.session.add(address_to_update)
                    incoming_address_ids.add(str(addr_data.id))
                else:
                    new_address = TripAddress(
                        trip_id=trip.id,
                        address_type=AddressTypeEnum.LOADING,
                        country_id=state.country_id,
                        state_id=addr_data.state_id,
                        district_id=addr_data.district_id,
                        city_id=addr_data.city_id,
                        location=addr_data.location,
                        pincode=addr_data.pincode,
                        sequence=idx,
                        created_by=user.id,
                        updated_by=user.id
                    )
                    self.session.add(new_address)

            # Process unloading addresses
            for idx, addr_data in enumerate(unloading_addresses, start=1):
                state = await self.session.get(State, addr_data.state_id)
                if not state:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"State with ID {addr_data.state_id} not found.")

                if addr_data.id and str(addr_data.id) in existing_addresses_map:
                    address_to_update = existing_addresses_map[str(addr_data.id)]
                    address_to_update.country_id = state.country_id
                    address_to_update.state_id = addr_data.state_id
                    address_to_update.district_id = addr_data.district_id
                    address_to_update.city_id = addr_data.city_id
                    address_to_update.location = addr_data.location
                    address_to_update.pincode = addr_data.pincode
                    address_to_update.sequence = idx
                    address_to_update.address_type = AddressTypeEnum.UNLOADING
                    address_to_update.updated_by = user.id
                    address_to_update.updated_at = datetime.utcnow()
                    self.session.add(address_to_update)
                    incoming_address_ids.add(str(addr_data.id))
                else:
                    new_address = TripAddress(
                        trip_id=trip.id,
                        address_type=AddressTypeEnum.UNLOADING,
                        country_id=state.country_id,
                        state_id=addr_data.state_id,
                        district_id=addr_data.district_id,
                        city_id=addr_data.city_id,
                        location=addr_data.location,
                        pincode=addr_data.pincode,
                        sequence=idx,
                        created_by=user.id,
                        updated_by=user.id
                    )
                    self.session.add(new_address)
            
            # Delete removed addresses
            for addr_id, address_to_delete in existing_addresses_map.items():
                if addr_id not in incoming_address_ids:
                    await self.session.delete(address_to_delete)
            
            self.session.add(trip)
            await self.session.commit()
            await self.session.refresh(trip)
            
            return await self.read(request, trip.id)

        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def delete(self, request: Request, id: UUID):
        """Delete trip"""
        try:
            trip = await self.get_object(id)
            await self.session.delete(trip)
            await self.session.commit()
            return {"detail": OBJECT_DELETED}
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def add_driver_to_trip_vendor(
        self,
        request: Request,
        trip_id: UUID,
        driver: TripDriverCreate
    ) -> ReadSchema:
        """Add a driver to a trip vendor."""
        try:
            user = request.state.user
            trip = await self.get_object(trip_id)
            if not trip.assigned_vendor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No vendor assigned to this trip."
                )
            trip_vendor = trip.assigned_vendor
            trip_driver = TripDriver(
                trip_vendor_id=trip_vendor.id,
                driver_name=driver.driver_name,
                driver_mobile_no=driver.driver_mobile_no,
                driver_licence_no=driver.driver_licence_no,
                driver_licence_expiry=driver.driver_licence_expiry,
                created_by=user.id,
                updated_by=user.id
            )

            self.session.add(trip_driver)
            await self.session.commit()
            await self.session.refresh(trip_driver)
            updated_trip = await self.get_object(trip_id)
            return self._to_read_schema(updated_trip, request)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {str(e)}")
        
    async def vehicle_loading_document_upload(
        self,
        request: Request,
        trip_id: UUID,
        eway_bill: UploadFile,
        invoice_copy: UploadFile,
        vehicle_image: UploadFile,
        lr_copy: UploadFile,
    ) -> ReadSchema:
        """Uploads loading documents for a trip and creates a TripDocument record."""
        try:
            user = request.state.user
            trip = await self.get_object(trip_id)

            if trip.trip_documents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Loading documents have already been uploaded for this trip."
                )

            upload_dir = f"uploads/trip_documents/{trip.id}/loading"

            trip_document = TripDocument(
                trip_id=trip.id,
                eway_bill=save_upload_file(eway_bill, upload_dir),
                invoice_copy=save_upload_file(invoice_copy, upload_dir),
                vehicle_image=save_upload_file(vehicle_image, upload_dir),
                lr_copy=save_upload_file(lr_copy, upload_dir),
                created_by=user.id,
                updated_by=user.id,
            )

            self.session.add(trip_document)
            await self.session.flush()

            previous_status = trip.status
            trip.status = TripStatusEnum.VEHICLE_LOADED
            trip.updated_by = user.id
            trip.updated_at = datetime.utcnow()

            history_entry = TripStatusHistory(
                trip_id=trip.id,
                previous_status=previous_status,
                current_status=TripStatusEnum.VEHICLE_LOADED,
                remarks="Vehicle Loaded",
                updated_by=user.id
            )
            self.session.add(history_entry)
            self.session.add(trip)

            await self.session.commit()

            if trip.status == TripStatusEnum.VEHICLE_LOADED:
                management_ids = await administrative_user_id(self.session, "management")

                notification_helper = NotificationHelper(self.session)
                await notification_helper.vehicle_loaded_notification(
                    user_ids=management_ids,
                    trip_id=trip.id,
                    trip_code=trip.trip_code,
                request=request
            )

            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {str(e)}")

    async def update_vehicle_loading_documents(
        self,
        request: Request,
        trip_id: UUID,
        eway_bill: Optional[UploadFile] = None,
        invoice_copy: Optional[UploadFile] = None,
        vehicle_image: Optional[UploadFile] = None,
        lr_copy: Optional[UploadFile] = None,
    ) -> ReadSchema:
        """Updates existing loading documents for a trip."""
        try:
            user = request.state.user
            trip = await self.get_object(trip_id)

            if not trip.trip_documents:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No loading documents found for this trip to update."
                )

            trip_document = trip.trip_documents
            upload_dir = f"uploads/trip_documents/{trip.id}/loading"

            if eway_bill:
                trip_document.eway_bill = save_upload_file(eway_bill, upload_dir)
            if invoice_copy:
                trip_document.invoice_copy = save_upload_file(invoice_copy, upload_dir)
            if vehicle_image:
                trip_document.vehicle_image = save_upload_file(vehicle_image, upload_dir)
            if lr_copy:
                trip_document.lr_copy = save_upload_file(lr_copy, upload_dir)

            trip_document.updated_by = user.id
            trip_document.updated_at = datetime.utcnow()

            self.session.add(trip_document)
            await self.session.commit()

            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {str(e)}")
        
    async def add_vehicle_unloading(
        self,
        request: Request,
        trip_id: UUID,
        pod_submit: Optional[UploadFile],
        other_charges: Decimal,
        is_shortage: Optional[bool] = None,
        is_damage: Optional[bool] = None,
        comments: Optional[str] = None,
    ) -> ReadSchema:
        try:
            user = request.state.user
            trip = await self.get_object(trip_id)
            trip_document = trip.trip_documents
            if not trip_document:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                    detail="No loading documents found for this trip. Please upload loading documents first.")
            
            if trip.status == TripStatusEnum.VEHICLE_UNLOADED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Status already assigned as 'Vehicle Unloaded'."
                )

            previous_status = trip.status
            trip.is_shortage = is_shortage
            trip.is_damage = is_damage

            trip_document.comments = comments
            trip_document.updated_by = user.id
            trip_document.updated_at = datetime.utcnow()

            if trip.assigned_vendor:
                trip.assigned_vendor.other_unloading_charges = other_charges

            self._create_payment_placeholder(
                trip=trip,
                vendor_id=trip.assigned_vendor.vendor_id,
                user_id=user.id,
                amount=other_charges,
                payment_type="Other Unloading Charges",
            )

            # First, set status to VEHICLE_UNLOADED
            trip.status = TripStatusEnum.VEHICLE_UNLOADED
            history_entry1 = TripStatusHistory(
                trip_id=trip.id,
                previous_status=previous_status,
                current_status=TripStatusEnum.VEHICLE_UNLOADED,
                remarks="Vehicle Unloaded",
                updated_by=user.id
            )
            self.session.add(history_entry1)
            await self.session.flush()

            # Then, if POD is submitted, update to POD_SUBMITTED
            if pod_submit:
                upload_dir = f"uploads/trip_documents/{trip.id}/unloading"
                trip_document.pod_submit = save_upload_file(pod_submit, upload_dir)
                
                previous_status_for_pod = TripStatusEnum.VEHICLE_UNLOADED
                trip.status = TripStatusEnum.POD_SUBMITTED

                history_entry2 = TripStatusHistory(
                    trip_id=trip.id,
                    previous_status=previous_status_for_pod,
                    current_status=TripStatusEnum.POD_SUBMITTED,
                    remarks="POD Submitted",
                    updated_by=user.id
                )
                self.session.add(history_entry2)

            self.session.add(trip)
            await self.session.commit()
            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred: {str(e)}")

    async def add_damage_shortage(
        self,
        request: Request,
        trip_id: UUID,
        deducted_amount: Decimal,
        deducted_details: Optional[str] = None,
    ) -> ReadSchema:
        """Adds damage/shortage details to a trip only if shortage/damage is reported."""
        try:
            trip = await self.get_object(trip_id)
            user = request.state.user

            if not (trip.is_shortage or trip.is_damage):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No shortage/damage reported. Please set 'is_shortage' or 'is_damage' to True for this trip before adding details."
                )
            
            trip.deducted_amount = deducted_amount
            trip.deducted_details = deducted_details

            self._create_payment_placeholder(
                trip=trip,
                vendor_id=trip.assigned_vendor.vendor_id,
                user_id=user.id,
                amount=deducted_amount,
                is_deduct_amount=True,
                payment_type="Deducted Amount",
            )

            self.session.add(trip)
            await self.session.commit()

            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def send_pod_to_customer(
        self,
        request: Request,
        trip_id: UUID,
        pod_file: Optional[UploadFile],
        send_to_customer: bool,
    ) -> ReadSchema:
        try:
            user = request.state.user
            trip = await self.get_object(trip_id)
            trip_document = trip.trip_documents
            if not trip_document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Trip documents not found."
                )

            if trip.status == TripStatusEnum.POD_SUBMITTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="POD is already submitted for this trip. No further actions are allowed."
                )

            if trip.pod_sent_to_customer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="POD already sent to customer."
                )

            if send_to_customer:
                if not pod_file:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="POD file is required to send to customer."
                    )
                upload_dir = f"uploads/trip_documents/{trip.id}/unloading"
                trip_document.pod_submit = save_upload_file(pod_file, upload_dir)
                trip_document.updated_by = user.id
                trip_document.updated_at = datetime.utcnow()

                trip.pod_sent_to_customer = True
                previous_status = trip.status
                trip.status = TripStatusEnum.POD_SUBMITTED
                trip.updated_by = user.id
                trip.updated_at = datetime.utcnow()

                history_entry = TripStatusHistory(
                    trip_id=trip.id,
                    previous_status=previous_status,
                    current_status=TripStatusEnum.POD_SUBMITTED,
                    remarks="POD Sent to Customer",
                    updated_by=user.id
                )
                self.session.add(history_entry)
            else:
                if pod_file:
                    upload_dir = f"uploads/trip_documents/{trip.id}/unloading"
                    trip_document.pod_submit = save_upload_file(pod_file, upload_dir)
                    trip_document.updated_by = user.id
                    trip_document.updated_at = datetime.utcnow()

                    trip.pod_sent_to_customer = True
                    previous_status = trip.status
                    trip.status = TripStatusEnum.POD_SUBMITTED
                    trip.updated_by = user.id
                    trip.updated_at = datetime.utcnow()

                    history_entry = TripStatusHistory(
                        trip_id=trip.id,
                        previous_status=previous_status,
                        current_status=TripStatusEnum.POD_SUBMITTED,
                        remarks="POD Sent to Customer",
                        updated_by=user.id
                    )
                    self.session.add(history_entry)

            self.session.add(trip)
            await self.session.commit()
            return await self.read(request, trip.id)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}"
            )

    async def list_pending_pod_trips(
        self,
        request: Request,
        page: int = 1,
        size: int = 10,
        search: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        time_period: TimePeriodEnum | None = None, 
        start_date: date | None = None, 
        end_date: date | None = None,
        trip_status: Optional[TripStatusEnum] = None,
    ) -> dict:
        """
        List trips where status is NOT POD_SUBMITTED with penalty tracking.
        """
        query = select(Model).filter(
            Model.status == TripStatusEnum.VEHICLE_UNLOADED,
        )

        if customer_id:
            query = query.filter(Model.customer_id == customer_id)
        
        if trip_status:
            query = query.filter(Model.status == trip_status)
        
        if search:
            query = query.filter(Model.trip_code.ilike(f"%{search}%"))

        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            query = query.where(Model.created_at >= start_date, Model.created_at <= end_date)

        # Get total count
        count_result = await self.session.execute(query)
        total = len(count_result.scalars().all())
        
        # Pagination
        offset = (page - 1) * size
        stmt = (
            query.options(
                selectinload(Model.status_history),
                selectinload(Model.assigned_vendor).joinedload(TripVendor.vendor),
                selectinload(Model.assigned_vendor).selectinload(TripVendor.drivers),
            )
            .order_by(Model.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        
        result = await self.session.execute(stmt)
        results = result.scalars().unique().all()
        
        # Build response with POD tracking data
        trip_list = []
        for trip in results:
            vendor_data = None
            if trip.assigned_vendor:
                driver = trip.assigned_vendor.drivers[0] if trip.assigned_vendor.drivers else None
                vendor_data = {
                    "id": trip.assigned_vendor.vendor.id,
                    "vendor_name": trip.assigned_vendor.vendor.vendor_name,
                    "vendor_code": trip.assigned_vendor.vendor.vendor_code,
                    "vehicle_no": trip.assigned_vendor.vehicle_no,
                    "driver_name": driver.driver_name if driver else "",
                    "driver_mobile_no": driver.driver_mobile_no if driver else "",
                }
            
            trip_list.append({
                "id": trip.id,
                "trip_code": trip.trip_code,
                "trip_date": trip.trip_date,
                "status": trip.status,
                "assigned_vendor": vendor_data,
                "vehicle_unloaded_date": trip.vehicle_unloaded_date,
                "pod_submission_last_date": trip.pod_submission_last_date,
                "pod_submitted_date": trip.pod_submitted_date,
                "pod_overdue_days": trip.pod_overdue_days,
                "pod_penalty_amount": trip.pod_penalty_amount,
            })
        
        # Pagination URLs
        next_url = (
            str(request.url.include_query_params(page=page + 1))
            if offset + size < total else None
        )
        previous_url = (
            str(request.url.include_query_params(page=page - 1))
            if page > 1 else None
        )
        
        return {
            "total": total,
            "next": next_url,
            "previous": previous_url,
            "results": trip_list
        }
