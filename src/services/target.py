# services/target.py

from typing import Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, case
from models import Trip
from models.trip import TripStatusEnum,TripVendor,TripStatusHistory
from models.advance_payment import AdvancePayment
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from datetime import date as date_type
from core import messages
from models import Target as Model, Branch
from models.employee import Employee
from models.target import TargetStatusEnum
from models.enums import TimePeriodEnum
from schemas import (
    TargetList as ListSchema,
    TargetRead as ReadSchema,
    TargetCreate as CreateSchema,
    TargetUpdate as UpdateSchema,
)
from schemas.target import  BranchPerformance, BranchPerformanceList, BranchPerformanceMetric, TargetStatusUpdate
from utils.date_helpers import get_date_range
from sqlalchemy import or_

OBJECT_NOT_FOUND = "Target not found"
OBJECT_EXIST = "Target already exists"
OBJECT_DELETED = "Target deleted successfully"


class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_object(self, id: UUID) -> Model:
        """Get target with full relationships for detail view"""
        statement = (
            select(Model)
            .options(
                selectinload(Model.branch).selectinload(Branch.country),
                selectinload(Model.branch).selectinload(Branch.state),
                selectinload(Model.branch).selectinload(Branch.district),
                selectinload(Model.branch).selectinload(Branch.city),
            )
            .where(Model.id == id)
        )
        result = await self.session.execute(statement)
        obj = result.scalars().first()
        
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=OBJECT_NOT_FOUND
            )
        return obj
    
    async def _save(self, obj: Model) -> Model:
        """Save object to database"""
        try:
            self.session.add(obj)
            await self.session.commit()
            await self.session.refresh(obj)
            return obj
        except IntegrityError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data integrity error: {str(e.orig)}"
            )

    async def _calculate_metrics(self, target: Model) -> dict:
        """Calculate trip, margin, and revenue metrics asynchronously"""
        
        # 1. Calculate Trip Metrics
        if target.status == TargetStatusEnum.CLOSED and target.achieved_trips is not None:
            achieved_trips = target.achieved_trips
        else:
            # Subquery for approved trips
            approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
            ).distinct().subquery()

            stmt = select(func.count(Trip.id)).where(
                Trip.branch_id == target.branch_id,
                Trip.trip_date >= target.start_date,
                Trip.trip_date <= target.end_date,
                Trip.id.in_(select(approved_trip_ids_sq))
            )
            achieved_trips = (await self.session.execute(stmt)).scalar() or 0

        target_trips = Decimal(target.no_of_trip) if target.no_of_trip else Decimal(0)
        achieved_trips_dec = Decimal(achieved_trips)
        percentage_trips = float((achieved_trips_dec / target_trips) * 100) if target_trips > 0 else 0.0

        trip_data = {
            "total_trip": target.no_of_trip,
            "achieved": achieved_trips,
            "achievement_percentage": round(percentage_trips, 2),
        }

        # 2. Calculate Revenue Metrics
        if target.status == TargetStatusEnum.CLOSED and target.achieved_revenue is not None:
            achieved_revenue = target.achieved_revenue
        else:
            approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
            ).distinct().subquery()

            stmt = select(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).where(
                Trip.branch_id == target.branch_id,
                Trip.trip_date >= target.start_date,
                Trip.trip_date <= target.end_date,
                Trip.id.in_(select(approved_trip_ids_sq))
            )
            achieved_revenue = (await self.session.execute(stmt)).scalar() or Decimal("0.00")

        percentage_revenue = float((achieved_revenue / target.total_revenue) * 100) if target.total_revenue > 0 else 0.0

        revenue_data = {
            "total_revenue": str(target.total_revenue),
            "achieved": str(achieved_revenue),
            "achievement_percentage": round(percentage_revenue, 2),
        }

        # 3. Calculate Margin Metrics
        if target.status == TargetStatusEnum.CLOSED and target.achieved_margin is not None:
            achieved_margin = target.achieved_margin
        else:
            approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
            ).distinct().subquery()

            # Total trip rate
            stmt_rate = select(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).where(
                Trip.branch_id == target.branch_id,
                Trip.trip_date >= target.start_date,
                Trip.trip_date <= target.end_date,
                Trip.id.in_(select(approved_trip_ids_sq))
            )
            total_trip_rate = (await self.session.execute(stmt_rate)).scalar() or Decimal("0.00")

            # Vendor payments
            stmt_payments = select(func.sum(AdvancePayment.amount)).join(Trip, AdvancePayment.trip_id == Trip.id).where(
                Trip.branch_id == target.branch_id,
                Trip.trip_date >= target.start_date,
                Trip.trip_date <= target.end_date,
                Trip.id.in_(select(approved_trip_ids_sq)),
                AdvancePayment.is_paid_amount == True
            )
            vendor_payments = (await self.session.execute(stmt_payments)).scalar() or Decimal("0.00")

            achieved_margin = total_trip_rate - vendor_payments

        percentage_margin = float((achieved_margin / target.total_margin) * 100) if target.total_margin > 0 else 0.0

        margin_data = {
            "total_margin": str(target.total_margin),
            "achieved": str(achieved_margin),
            "achievement_percentage": round(percentage_margin, 2),
        }

        return {
            "trip": trip_data,
            "revenue": revenue_data,
            "margin": margin_data
        }

    async def _calculate_achieved_values(self, target: Model) -> dict:
        """Calculate achieved values for closing targets"""
        
        # Achieved Trips
        stmt_trips = select(func.count(Trip.id)).where(
            Trip.branch_id == target.branch_id,
            Trip.trip_date >= target.start_date,
            Trip.trip_date <= target.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        )
        achieved_trips = (await self.session.execute(stmt_trips)).scalar() or 0

        # Achieved Revenue
        stmt_revenue = select(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).where(
            Trip.branch_id == target.branch_id,
            Trip.trip_date >= target.start_date,
            Trip.trip_date <= target.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        )
        achieved_revenue = (await self.session.execute(stmt_revenue)).scalar() or Decimal("0.00")

        # Achieved Margin
        # Get trips with vendor assignments
        stmt_trips_margin = select(Trip).options(selectinload(Trip.assigned_vendor)).join(TripVendor).where(
            Trip.branch_id == target.branch_id,
            Trip.trip_date >= target.start_date,
            Trip.trip_date <= target.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        )
        trips = (await self.session.execute(stmt_trips_margin)).scalars().all()
        
        total_margin = Decimal("0.00")
        for trip in trips:
            if trip.assigned_vendor:
                customer_rate = trip.trip_rate
                vendor_rate = trip.assigned_vendor.trip_rate
                margin = customer_rate - vendor_rate
                total_margin += margin

        return {
            "achieved_trips": achieved_trips,
            "achieved_revenue": achieved_revenue,
            "achieved_margin": total_margin
        }
    async def list(
        self, 
        request: Request, 
        page=1, 
        size=10, 
        search: str | None = None,
        branch_id: UUID | None = None,
        status: TargetStatusEnum | None = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date_type | None = None,
        end_date: date_type | None = None,
    ) -> ListSchema:
        """List targets with filters"""
        
        user = request.state.user
        
        # ✅ Check if user is Branch Manager and get their branch
        user_branch_id = await self._get_user_branch_id(user)
        
        # ✅ Auto-close expired targets and save achieved values
        today = date_type.today()
        expired_statement = (
            select(Model)
            .where(
                Model.end_date < today,
                Model.status.in_([TargetStatusEnum.PENDING, TargetStatusEnum.APPROVED])
            )
        )
        
        # ✅ If Branch Manager, only close their branch targets
        if user_branch_id:
            expired_statement = expired_statement.where(Model.branch_id == user_branch_id)
        
        expired_result = await self.session.execute(expired_statement)
        expired_targets = expired_result.scalars().all()
        
        for target in expired_targets:
            # ✅ Use async helper to calculate and save achieved values
            achieved_values = await self._calculate_achieved_values(target)
            target.achieved_trips = achieved_values["achieved_trips"]
            target.achieved_revenue = achieved_values["achieved_revenue"]
            target.achieved_margin = achieved_values["achieved_margin"]
            target.status = TargetStatusEnum.CLOSED
            target.updated_at = datetime.utcnow()
        
        if expired_targets:
            await self.session.commit()
        
        # ✅ Build query with branch filtering
        statement = select(Model).options(
            selectinload(Model.branch).load_only(Branch.id, Branch.code, Branch.name),
        )
        
        # ✅ If user is Branch Manager, force filter by their branch
        if user_branch_id:
            statement = statement.where(Model.branch_id == user_branch_id)
            # Ignore branch_id filter parameter for Branch Managers
        else:
            # ✅ Apply branch_id filter only if not Branch Manager
            if branch_id:
                statement = statement.where(Model.branch_id == branch_id)
        
        if status:
            statement = statement.where(Model.status == status)
        
        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            statement = statement.where(Model.created_at >= start_date, Model.created_at <= end_date)
        
        if search:
            statement = statement.join(Branch).where(Branch.name.ilike(f"%{search}%"))
        
        # Paginate
        count_stmt = select(func.count()).select_from(statement.subquery())
        total = (await self.session.execute(count_stmt)).scalar()

        offset = (page - 1) * size
        statement = statement.order_by(Model.start_date.desc(), Model.end_date.desc())
        statement = statement.offset(offset).limit(size)
        results = (await self.session.execute(statement)).scalars().all()

        next_url = str(request.url.include_query_params(page=page + 1)) if offset + size < total else None
        previous_url = str(request.url.include_query_params(page=page - 1)) if page > 1 else None

        # ✅ Calculate metrics for each result
        read_results = []
        for target in results:
            t_dict = target.dict()
            metrics = await self._calculate_metrics(target)
            t_dict.update(metrics)
            t_dict['branch_info'] = target.branch_info
            read_results.append(t_dict)

        return ListSchema(
            total=total,
            next=next_url,
            previous=previous_url,
            results=read_results
        )


    
    # services/target.py

    
    async def _get_user_branch_id(self, user) -> UUID | None:
        """
        Get branch_id for Branch Manager users.
        Returns None if user is not a Branch Manager or is admin.
        """
        # Check if user has a role
        if not user.role:
            return None
        
        # ✅ FIX: user.role is a Role object, access its name attribute
        if user.role.name.lower() != "branch manager":
            return None
        
        # Get user's branch from employee record
        statement = (
            select(Employee)
            .where(Employee.user_id == user.id)
            .where(Employee.is_active == True)
        )
        result = await self.session.execute(statement)
        employee = result.scalars().first()
        
        if not employee or not employee.branch_id:
            return None
        
        return employee.branch_id


    async def read(self, request: Request, id: UUID) -> ReadSchema:
        """Get target details"""
        obj = await self.get_object(id)
        t_dict = obj.dict()
        metrics = await self._calculate_metrics(obj)
        t_dict.update(metrics)
        t_dict['branch_info'] = obj.branch_info
        t_dict['branch_detail'] = obj.branch_detail
        return t_dict


    async def create(self, request: Request, item: CreateSchema) -> ReadSchema:
        """Create new target"""
        user = request.state.user
        
      
        branch = await self.session.get(Branch, item.branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found"
            )
        
       
        pending_stmt = (
            select(Model)
            .where(
                Model.branch_id == item.branch_id,
                Model.status == TargetStatusEnum.PENDING
            )
        )
        existing_pending = (await self.session.execute(pending_stmt)).scalars().first()
        
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Branch already has a pending target . Please approve or reject it before creating a new one."
            )
        
       
       
        approved_stmt = (
            select(Model)
            .where(
                Model.branch_id == item.branch_id,
                Model.status == TargetStatusEnum.APPROVED,
                or_(
                    (Model.start_date <= item.end_date) & (Model.end_date >= item.start_date)
                )
            )
        )
        existing_approved = (await self.session.execute(approved_stmt)).scalars().first()
        
        if existing_approved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Branch already has an approved target for the given date range ({existing_approved.start_date} to {existing_approved.end_date})"
            )
        
        # Create new target
        obj = Model(
            **item.dict(),
            created_by=user.id,
            updated_by=user.id
        )
        
        
        obj = await self._save(obj)
        obj = await self.get_object(obj.id)
        
        t_dict = obj.dict()
        metrics = await self._calculate_metrics(obj)
        t_dict.update(metrics)
        t_dict['branch_info'] = obj.branch_info
        t_dict['branch_detail'] = obj.branch_detail
        return t_dict

    async def update(self, request: Request, id: UUID, item: UpdateSchema) -> ReadSchema:
        """Update target (PUT - all fields required)"""
        user = request.state.user
        obj = await self.get_object(id)
        
        if obj.status != TargetStatusEnum.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update target with status {obj.status}"
            )
        
        update_data = item.dict()
        for key, value in update_data.items():
            setattr(obj, key, value)
        
        obj.updated_by = user.id
        obj.updated_at = datetime.utcnow()
        
       
        obj = await self._save(obj)
        obj = await self.get_object(obj.id)
        
        t_dict = obj.dict()
        metrics = await self._calculate_metrics(obj)
        t_dict.update(metrics)
        t_dict['branch_info'] = obj.branch_info
        t_dict['branch_detail'] = obj.branch_detail
        return t_dict

    async def delete(self, request: Request, id: UUID):
        """Delete target"""
        obj = await self.get_object(id)
        
        # if obj.status not in [TargetStatusEnum.PENDING, TargetStatusEnum.REJECTED]:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail=f"Cannot delete target with status {obj.status}"
        #     )
        
        await self.session.delete(obj)
        await self.session.commit()
        return {"detail": OBJECT_DELETED}
    
    async def update_status(
        self, 
        request: Request, 
        id: UUID, 
        data: TargetStatusUpdate
    ) -> ReadSchema:
        """Update target status"""
        user = request.state.user
        target = await self.get_object(id)
        
        if target.status == TargetStatusEnum.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change status of closed target"
            )
        
        if data.status == TargetStatusEnum.REJECTED:
            if not data.rejection_reason or data.rejection_reason.strip() == "":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rejection reason is required when status is Rejected"
                )
            target.rejection_reason = data.rejection_reason
        else:
            target.rejection_reason = None
        
        target.status = data.status
        target.updated_by = user.id
        target.updated_at = datetime.utcnow()
        
        
        obj = await self._save(target)
        obj = await self.get_object(obj.id)
        
        t_dict = obj.dict()
        metrics = await self._calculate_metrics(obj)
        t_dict.update(metrics)
        t_dict['branch_info'] = obj.branch_info
        t_dict['branch_detail'] = obj.branch_detail
        return t_dict
    
    async def get_branch_performance(
        self,
        request: Request,
        branch_id: Optional[UUID] = None,
        time_period: TimePeriodEnum | None = None,
        start_date: date_type | None = None,
        end_date: date_type | None = None,
    ) -> BranchPerformanceList:
        """
        Get branch-wise performance metrics based on approved/closed targets.
        Uses async helper for calculations.
        """
        user = request.state.user
        
        # Get user's branch if Branch Manager
        user_branch_id = await self._get_user_branch_id(user)
        
        # Build base query for approved/closed/pending targets
        statement = (
            select(Model)
            .options(
                selectinload(Model.branch).load_only(Branch.id, Branch.code, Branch.name)
            )
            .where(Model.status.in_([
                TargetStatusEnum.APPROVED, 
                TargetStatusEnum.CLOSED,
                TargetStatusEnum.PENDING
            ]))
        )
        
        # If Branch Manager, filter by their branch
        if user_branch_id:
            statement = statement.where(Model.branch_id == user_branch_id)
        # Otherwise, apply optional branch filter
        elif branch_id:
            statement = statement.where(Model.branch_id == branch_id)
        
        # Apply time period or date range filtering
        if time_period:
            start_date, end_date = get_date_range(time_period, start_date, end_date)

        if start_date and end_date and not time_period:
            start_date = datetime.combine(start_date, datetime.min.time())
            end_date = datetime.combine(end_date, datetime.max.time())

        if start_date and end_date:
            # Filter by target's date range overlapping with the query range
            statement = statement.where(
                or_(
                    (Model.start_date >= start_date.date()) & (Model.start_date <= end_date.date()),
                    (Model.end_date >= start_date.date()) & (Model.end_date <= end_date.date()),
                    (Model.start_date <= start_date.date()) & (Model.end_date >= end_date.date())
                )
            )
        
        result = await self.session.execute(statement)
        targets = result.scalars().all()
        
        # ✅ Build performance data using async helper
        results = []
        for target in targets:
            metrics = await self._calculate_metrics(target)
            trip_data = metrics["trip"]
            margin_data = metrics["margin"]
            revenue_data = metrics["revenue"]
            
            results.append(BranchPerformance(
                branch_id=target.branch_id,
                branch_code=target.branch.code,
                branch_name=target.branch.name,
                trips=BranchPerformanceMetric(
                    target=Decimal(trip_data["total_trip"]),
                    achieved=Decimal(trip_data["achieved"]),
                ),
                revenue=BranchPerformanceMetric(
                    target=Decimal(revenue_data["total_revenue"]),
                    achieved=Decimal(revenue_data["achieved"]),
                ),
                margin=BranchPerformanceMetric(
                    target=Decimal(margin_data["total_margin"]),
                    achieved=Decimal(margin_data["achieved"]),
                ),
                target_status=target.status.value,
                target_period=f"{target.start_date} to {target.end_date}"
            ))
        
        return BranchPerformanceList(
            total=len(results),
            results=results
        )
