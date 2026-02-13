# models/target.py

from typing import TYPE_CHECKING, Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from sqlmodel import Field, Relationship, Column
from sqlalchemy import Numeric, func, select
from db.base import BaseTable
import enum
from sqlalchemy.orm import Session
if TYPE_CHECKING:
    from .branch import Branch

class TargetStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CLOSED = "Closed"

class Target(BaseTable, table=True):
    __tablename__ = 'marketline_targets'

    branch_id: UUID = Field(foreign_key="marketline_branches.id", nullable=False)
    no_of_trip: int = Field(nullable=False, gt=0)
    
    # ✅ Remove nullable when using sa_column
    total_margin: Decimal = Field(
        sa_column=Column(Numeric(15, 2), nullable=False)
    )
    total_revenue: Decimal = Field(
        sa_column=Column(Numeric(15, 2), nullable=False)
    )
    
    start_date: date = Field(nullable=False)
    end_date: date = Field(nullable=False)
    status: TargetStatusEnum = Field(default=TargetStatusEnum.PENDING, nullable=False)
    
    # Optional fields
    rejection_reason: Optional[str] = Field(default=None, max_length=500)
    achieved_trips: Optional[int] = Field(default=None, nullable=True)
    
    achieved_margin: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(15, 2), nullable=True)
    )
    
    achieved_revenue: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(15, 2), nullable=True)
    )
    
    
    # Relationships
    branch: "Branch" = Relationship(sa_relationship_kwargs={"lazy": "joined"})
    
   
    
    @property
    def trip(self) -> dict:
        """Return trip-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_trips is not None:
            achieved = self.achieved_trips
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            session = Session.object_session(self)
            if not session:
                achieved = 0
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Count trips matching the target's criteria that are in the approved list
                achieved = session.query(func.count(Trip.id)).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or 0
        
        target = Decimal(self.no_of_trip) if self.no_of_trip else Decimal(0)

        
        achieved_decimal = Decimal(achieved)
        percentage = float((achieved_decimal / target) * 100) if target > 0 else 0.0
        
        return {
            "total_trip": self.no_of_trip,
            "achieved": achieved,
            "achievement_percentage": round(percentage, 2),
        }

    @property
    def margin(self) -> dict:
        """Return margin-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_margin is not None:
            achieved = self.achieved_margin
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            from models.advance_payment import AdvancePayment
            session = Session.object_session(self)
            if not session:
                achieved = Decimal("0.00")
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Calculate total trip_rate for those trips
                total_trip_rate = session.query(
                    func.sum(Trip.trip_rate + Trip.loading_unloading_charges)
                ).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or Decimal("0.00")

                # Calculate total amount paid to vendors for those trips
                vendor_payments = session.query(
                    func.sum(AdvancePayment.amount)
                ).join(Trip, AdvancePayment.trip_id == Trip.id).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq)),
                    AdvancePayment.is_paid_amount == True  # Ensure only paid amounts are included
                ).scalar() or Decimal("0.00")

                # Calculate margin
                achieved = total_trip_rate - vendor_payments



        percentage = float((achieved / self.total_margin) * 100) if self.total_margin > 0 else 0.0
        
        return {
            "total_margin": str(self.total_margin),
            "achieved": str(achieved),
            "achievement_percentage": round(percentage, 2),
        }

    @property
    def revenue(self) -> dict:
        """Return revenue-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_revenue is not None:
            achieved = self.achieved_revenue
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            session = Session.object_session(self)
            if not session:
                achieved = Decimal("0.00")
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Sum the trip_rate for trips matching the target's criteria that are in the approved list
                achieved = session.query(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or Decimal("0.00")
        
        percentage = float((achieved / self.total_revenue) * 100) if self.total_revenue > 0 else 0.0
        
        return {
            "total_revenue": str(self.total_revenue),
            "achieved": str(achieved),
            "achievement_percentage": round(percentage, 2),
        }
    
    @property
    def trip(self) -> dict:
        """Return trip-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_trips is not None:
            achieved = self.achieved_trips
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            session = Session.object_session(self)
            # Safety check for async session
            if not session or not hasattr(session, 'query'):
                achieved = 0
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Count trips matching the target's criteria that are in the approved list
                achieved = session.query(func.count(Trip.id)).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or 0
        
        target = Decimal(self.no_of_trip) if self.no_of_trip else Decimal(0)

        
        achieved_decimal = Decimal(achieved)
        percentage = float((achieved_decimal / target) * 100) if target > 0 else 0.0
        
        return {
            "total_trip": self.no_of_trip,
            "achieved": achieved,
            "achievement_percentage": round(percentage, 2),
        }

    @property
    def margin(self) -> dict:
        """Return margin-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_margin is not None:
            achieved = self.achieved_margin
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            from models.advance_payment import AdvancePayment
            session = Session.object_session(self)
            # Safety check for async session
            if not session or not hasattr(session, 'query'):
                achieved = Decimal("0.00")
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Calculate total trip_rate for those trips
                total_trip_rate = session.query(
                    func.sum(Trip.trip_rate + Trip.loading_unloading_charges)
                ).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or Decimal("0.00")

                # Calculate total amount paid to vendors for those trips
                vendor_payments = session.query(
                    func.sum(AdvancePayment.amount)
                ).join(Trip, AdvancePayment.trip_id == Trip.id).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq)),
                    AdvancePayment.is_paid_amount == True  # Ensure only paid amounts are included
                ).scalar() or Decimal("0.00")

                # Calculate margin
                achieved = total_trip_rate - vendor_payments



        percentage = float((achieved / self.total_margin) * 100) if self.total_margin > 0 else 0.0
        
        return {
            "total_margin": str(self.total_margin),
            "achieved": str(achieved),
            "achievement_percentage": round(percentage, 2),
        }

    @property
    def revenue(self) -> dict:
        """Return revenue-related data"""
        # If CLOSED and has recorded value, use it
        if self.status == TargetStatusEnum.CLOSED and self.achieved_revenue is not None:
            achieved = self.achieved_revenue
        else:
            from models.trip import Trip, TripStatusEnum, TripStatusHistory
            session = Session.object_session(self)
            # Safety check for async session
            if not session or not hasattr(session, 'query'):
                achieved = Decimal("0.00")
            else:
                # Subquery to find trip IDs that have ever had the FLIT_RATE_APPROVE status
                approved_trip_ids_sq = select(TripStatusHistory.trip_id).where(
                    TripStatusHistory.current_status == TripStatusEnum.FLEET_RATE_APPROVE
                ).distinct().subquery()

                # Sum the trip_rate for trips matching the target's criteria that are in the approved list
                achieved = session.query(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).filter(
                    Trip.branch_id == self.branch_id,
                    Trip.trip_date >= self.start_date,
                    Trip.trip_date <= self.end_date,
                    Trip.id.in_(select(approved_trip_ids_sq))
                ).scalar() or Decimal("0.00")
        
        percentage = float((achieved / self.total_revenue) * 100) if self.total_revenue > 0 else 0.0
        
        return {
            "total_revenue": str(self.total_revenue),
            "achieved": str(achieved),
            "achievement_percentage": round(percentage, 2),
        }
    
    @property
    def branch_info(self) -> dict:
        """Return branch basic info for listing"""
        if not self.branch:
            return None
        return {
            "code": self.branch.code,
            "name": self.branch.name,
        }
    
    @property
    def branch_detail(self) -> dict:
        """Return branch with address for detail view"""
        if not self.branch:
            return None
        return {
            "id": self.branch.id,
            "code": self.branch.code,
            "name": self.branch.name,
            "address": self.branch.address,  
        }

    @property
    def calculated_achieved_trips(self) -> int:
        """
        Calculate actual achieved trips from Trip model.
        Count trips with VEHICLE_UNLOADED status or beyond for this branch within target period.
        """
        from models.trip import Trip, TripStatusEnum
        from sqlalchemy import func
        
        # If manually set (e.g., when CLOSED), use that value
        if self.status == TargetStatusEnum.CLOSED and self.achieved_trips is not None:
            return self.achieved_trips
        
        # Get session from self (SQLModel provides this)
        session = Session.object_session(self)
        if not session or not hasattr(session, 'query'):
            return 0
        
        # Count trips for this branch within target period with VEHICLE_UNLOADED+ status
        count = session.query(func.count(Trip.id)).filter(
            Trip.branch_id == self.branch_id,
            Trip.trip_date >= self.start_date,
            Trip.trip_date <= self.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        ).scalar()
        
        return count or 0
    
    @property
    def calculated_achieved_revenue(self) -> Decimal:
        """
        Calculate actual achieved revenue from Trip model.
        Sum of customer trip_rate for unloaded trips within target period.
        """
        from models.trip import Trip, TripStatusEnum
        from sqlalchemy import func
        
        # If manually set (e.g., when CLOSED), use that value
        if self.status == TargetStatusEnum.CLOSED and self.achieved_revenue is not None:
            return self.achieved_revenue
        
        session = Session.object_session(self)
        if not session or not hasattr(session, 'query'):
            return Decimal("0.00")
        
        # Sum trip_rate (customer rate) for unloaded trips
        total = session.query(func.sum(Trip.trip_rate + Trip.loading_unloading_charges)).filter(
            Trip.branch_id == self.branch_id,
            Trip.trip_date >= self.start_date,
            Trip.trip_date <= self.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        ).scalar()
        
        return total or Decimal("0.00")
    
    @property
    def calculated_achieved_margin(self) -> Decimal:
        """
        Calculate actual achieved margin from Trip model.
        Sum of (customer trip_rate - vendor trip_rate) for unloaded trips within target period.
        """
        from models.trip import Trip, TripVendor, TripStatusEnum
        from sqlalchemy import func
        
        # If manually set (e.g., when CLOSED), use that value
        if self.status == TargetStatusEnum.CLOSED and self.achieved_margin is not None:
            return self.achieved_margin
        
        session = Session.object_session(self)
        if not session or not hasattr(session, 'query'):
            return Decimal("0.00")
        
        # Get trips with vendor assignments
        trips = session.query(Trip).join(TripVendor).filter(
            Trip.branch_id == self.branch_id,
            Trip.trip_date >= self.start_date,
            Trip.trip_date <= self.end_date,
            Trip.status.in_([
                TripStatusEnum.VEHICLE_UNLOADED,
                TripStatusEnum.POD_SUBMITTED,
                TripStatusEnum.COMPLETED
            ])
        ).all()
        
        # Calculate margin for each trip
        total_margin = Decimal("0.00")
        for trip in trips:
            if trip.assigned_vendor:
                customer_rate = trip.trip_rate
                vendor_rate = trip.assigned_vendor.trip_rate
                margin = customer_rate - vendor_rate
                total_margin += margin
        
        return total_margin
    class Config:
        json_schema_extra = {
            "example": {
                "branch_id": "uuid",
                "no_of_trip": 100,
                "total_margin": 50000.00,
                "total_revenue": 500000.00,
                "start_date": "2025-11-01",
                "end_date": "2025-11-30",
                "status": "Pending"
            }
        }