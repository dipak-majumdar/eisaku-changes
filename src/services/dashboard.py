
from uuid import UUID
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, cast, Date, case, select, select
from typing import List, Dict

from models import Customer, Vendor, Complaint, Target, Employee
from models.trip import Trip, TripStatusEnum
from models.vendor import VendorStatusEnum
from models.vendor_registation import VendorRegistration
from models.customer import CustomerStatusEnum
from models.vendor_registation import VendorRegistrationStatusEnum
from models.complaint import ComplaintStatusEnum
from models.target import TargetStatusEnum
from models.enums import TimePeriodEnum
from schemas.dashboard import (
    ComplaintStats,
    DashboardData,
    DashboardResponse, 
   ComplaintDashboard,
   ComplaintDateWiseStats,
   CustomerDashboard,
   CustomerDateWiseStats,
    CustomerStats,
    VendorStats,
    TargetStats,
    TripStats,
    VendorRegistrationStats,
   VendorDashboard,
   VendorDateWiseStats,
   VendorRegistrationDashboard,
   VendorRegistrationDateWiseStats,
   TargetDashboard,
   TargetDateWiseStats,
   TripDashboard,
   TripDateWiseStats
)
from utils.date_helpers import get_date_range

class Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _get_date_list(self, start_date: date, end_date: date) -> List[date]:
        """Generate list of dates between start and end"""
        date_list = []
        current = start_date
        while current <= end_date:
            date_list.append(current)
            current += timedelta(days=1)
        return date_list

    async def _get_customer_stats(self, start_date: datetime, end_date: datetime) -> CustomerDashboard:
        """Optimized customer statistics with single query"""
        
        # ✅ Single query for all overall stats
        overall_stmt = select(
            func.count(Customer.id).label('total'),
            func.sum(case((Customer.status == CustomerStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((Customer.status == CustomerStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((Customer.status == CustomerStatusEnum.REJECTED, 1), else_=0)).label('rejected')
        ).where(
            Customer.created_at.between(start_date, end_date)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()
        
        # ✅ Single query for date-wise stats (GROUP BY date)
        date_wise_stmt = select(
            cast(Customer.created_at, Date).label('date'),
            func.count(Customer.id).label('total'),
            func.sum(case((Customer.status == CustomerStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((Customer.status == CustomerStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((Customer.status == CustomerStatusEnum.REJECTED, 1), else_=0)).label('rejected')
        ).where(
            Customer.created_at.between(start_date, end_date)
        ).group_by(
            cast(Customer.created_at, Date)
        )
        date_wise_result = await self.session.execute(date_wise_stmt)
        date_wise_query = date_wise_result.all()
        
        # Convert to dict for fast lookup
        date_stats_dict = {
            row.date: CustomerDateWiseStats(
                date=row.date,
                total=row.total or 0,
                pending=row.pending or 0,
                approved=row.approved or 0,
                rejected=row.rejected or 0
            ) for row in date_wise_query
        }
        
        # Fill in missing dates with zeros
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = [
            date_stats_dict.get(d, CustomerDateWiseStats(date=d, total=0))
            for d in date_list
        ]
        
        return CustomerDashboard(
            stats=CustomerStats(
                total=overall_stats.total or 0,
                pending=overall_stats.pending or 0,
                approved=overall_stats.approved or 0,
                rejected=overall_stats.rejected or 0
            ),
            results=results
        )

    async def _get_vendor_stats(self, start_date: datetime, end_date: datetime) -> VendorDashboard:
        """Optimized vendor statistics (status + is_active)"""
        
        # ✅ Single query for overall stats
        overall_stmt = select(
            func.count(Vendor.id).label('total'),
            func.sum(case((Vendor.status == VendorStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((Vendor.status == VendorStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((Vendor.status == VendorStatusEnum.REJECTED, 1), else_=0)).label('rejected'),
            func.sum(case((Vendor.is_active == True, 1), else_=0)).label('active'),
            func.sum(case((Vendor.is_active == False, 1), else_=0)).label('inactive')
        ).where(
            Vendor.created_at.between(start_date, end_date)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()
        
        # ✅ Single query for date-wise stats
        date_wise_stmt = select(
            cast(Vendor.created_at, Date).label('date'),
            func.count(Vendor.id).label('total'),
            func.sum(case((Vendor.status == VendorStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((Vendor.status == VendorStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((Vendor.status == VendorStatusEnum.REJECTED, 1), else_=0)).label('rejected'),
            func.sum(case((Vendor.is_active == True, 1), else_=0)).label('active'),
            func.sum(case((Vendor.is_active == False, 1), else_=0)).label('inactive')
        ).where(
            Vendor.created_at.between(start_date, end_date)
        ).group_by(
            cast(Vendor.created_at, Date)
        )
        date_wise_result = await self.session.execute(date_wise_stmt)
        date_wise_query = date_wise_result.all()
        
        date_stats_dict = {
            row.date: VendorDateWiseStats(
                date=row.date,
                total=row.total or 0,
                pending=row.pending or 0,
                approved=row.approved or 0,
                rejected=row.rejected or 0,
                active=row.active or 0,
                inactive=row.inactive or 0
            ) for row in date_wise_query
        }
        
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = [
            date_stats_dict.get(d, VendorDateWiseStats(date=d, total=0))
            for d in date_list
        ]
        
        return VendorDashboard(
            stats=VendorStats(
                total=overall_stats.total or 0,
                pending=overall_stats.pending or 0,
                approved=overall_stats.approved or 0,
                rejected=overall_stats.rejected or 0,
                active=overall_stats.active or 0,
                inactive=overall_stats.inactive or 0
            ),
            results=results
        )

    async def _get_vendor_registration_stats(self, start_date: datetime, end_date: datetime) -> VendorRegistrationDashboard:
        """Optimized vendor registration statistics"""
        
        overall_stmt = select(
            func.count(VendorRegistration.id).label('total'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.REJECTED, 1), else_=0)).label('rejected')
        ).where(
            VendorRegistration.created_at.between(start_date, end_date)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()
        
        date_wise_stmt = select(
            cast(VendorRegistration.created_at, Date).label('date'),
            func.count(VendorRegistration.id).label('total'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((VendorRegistration.status == VendorRegistrationStatusEnum.REJECTED, 1), else_=0)).label('rejected')
        ).where(
            VendorRegistration.created_at.between(start_date, end_date)
        ).group_by(
            cast(VendorRegistration.created_at, Date)
        )
        date_wise_result = await self.session.execute(date_wise_stmt)
        date_wise_query = date_wise_result.all()
        
        date_stats_dict = {
            row.date: VendorRegistrationDateWiseStats(
                date=row.date,
                total=row.total or 0,
                pending=row.pending or 0,
                approved=row.approved or 0,
                rejected=row.rejected or 0
            ) for row in date_wise_query
        }
        
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = [
            date_stats_dict.get(d, VendorRegistrationDateWiseStats(date=d, total=0))
            for d in date_list
        ]
        
        return VendorRegistrationDashboard(
            stats=VendorRegistrationStats(
                total=overall_stats.total or 0,
                pending=overall_stats.pending or 0,
                approved=overall_stats.approved or 0,
                rejected=overall_stats.rejected or 0
            ),
            results=results
        )

    async def _get_complaint_stats(self, start_date: datetime, end_date: datetime) -> ComplaintDashboard:
        """Optimized complaint statistics"""
        
        overall_stmt = select(
            func.count(Complaint.id).label('total'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.OPEN, 1), else_=0)).label('open'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.INPROGRESS, 1), else_=0)).label('inprogress'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.CLOSED, 1), else_=0)).label('closed')
        ).where(
            Complaint.created_at.between(start_date, end_date)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()
        
        date_wise_stmt = select(
            cast(Complaint.created_at, Date).label('date'),
            func.count(Complaint.id).label('total'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.OPEN, 1), else_=0)).label('open'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.INPROGRESS, 1), else_=0)).label('inprogress'),
            func.sum(case((Complaint.status == ComplaintStatusEnum.CLOSED, 1), else_=0)).label('closed')
        ).where(
            Complaint.created_at.between(start_date, end_date)
        ).group_by(
            cast(Complaint.created_at, Date)
        )
        date_wise_result = await self.session.execute(date_wise_stmt)
        date_wise_query = date_wise_result.all()
        
        date_stats_dict = {
            row.date: ComplaintDateWiseStats(
                date=row.date,
                total=row.total or 0,
                open=row.open or 0,
                inprogress=row.inprogress or 0,
                closed=row.closed or 0
            ) for row in date_wise_query
        }
        
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = [
            date_stats_dict.get(d, ComplaintDateWiseStats(date=d, total=0))
            for d in date_list
        ]
        
        return ComplaintDashboard(
            stats=ComplaintStats(
                total=overall_stats.total or 0,
                open=overall_stats.open or 0,
                inprogress=overall_stats.inprogress or 0,
                closed=overall_stats.closed or 0
            ),
            results=results
        )
    
    async def _get_trip_stats(self, start_date: datetime, end_date: datetime) -> TripDashboard:
        """Get trip statistics for dashboard, filtering only specific statuses"""
        
        # ✅ Define statuses to include in total count
        included_statuses = [
            TripStatusEnum.PENDING,
            TripStatusEnum.APPROVED,
            TripStatusEnum.IN_TRANSIT,
            TripStatusEnum.COMPLETED,
            TripStatusEnum.REJECTED
        ]
        
        # Overall stats - only count trips with included statuses
        overall_stmt = select(
            func.count(Trip.id).label('total'),
            func.sum(case((Trip.status == TripStatusEnum.PENDING, 1), else_=0)).label('pending'),
            func.sum(case((Trip.status == TripStatusEnum.APPROVED, 1), else_=0)).label('approved'),
            func.sum(case((Trip.status == TripStatusEnum.IN_TRANSIT, 1), else_=0)).label('in_transit'),
            func.sum(case((Trip.status == TripStatusEnum.COMPLETED, 1), else_=0)).label('completed'),
            func.sum(case((Trip.status == TripStatusEnum.REJECTED, 1), else_=0)).label('rejected'),
        ).where(
            Trip.trip_date.between(start_date, end_date),
            Trip.status.in_(included_statuses)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()

        # Use single query per day with aggregation instead of multiple count queries
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = []
        for day in date_list:
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            day_stmt = select(
                func.count(Trip.id).label('total'),
                func.sum(case((Trip.status == TripStatusEnum.PENDING, 1), else_=0)).label('pending'),
                func.sum(case((Trip.status == TripStatusEnum.IN_TRANSIT, 1), else_=0)).label('in_transit'),
                func.sum(case((Trip.status == TripStatusEnum.COMPLETED, 1), else_=0)).label('completed'),
                func.sum(case((Trip.status == TripStatusEnum.APPROVED, 1), else_=0)).label('approved'),
                func.sum(case((Trip.status == TripStatusEnum.REJECTED, 1), else_=0)).label('rejected'),
            ).where(
                Trip.trip_date.between(day_start, day_end),
                Trip.status.in_(included_statuses)
            )
            day_result = await self.session.execute(day_stmt)
            day_stats = day_result.one()
            
            results.append(
                TripDateWiseStats(
                    date=day,
                    total=day_stats.total or 0,
                    pending=day_stats.pending or 0,
                    in_transit=day_stats.in_transit or 0,
                    completed=day_stats.completed or 0,
                    approved=day_stats.approved or 0,
                    rejected=day_stats.rejected or 0,
                )
            )

        return TripDashboard(
            stats=TripStats(
                total=overall_stats.total or 0,
                pending=overall_stats.pending or 0,
                in_transit=overall_stats.in_transit or 0,
                completed=overall_stats.completed or 0,
                approved=overall_stats.approved or 0,
                rejected=overall_stats.rejected or 0,
            ),
            results=results
        )

    async def _get_target_stats(self, start_date: datetime, end_date: datetime) -> TargetDashboard:
        """Optimized target statistics"""
        
        overall_stmt = select(
            func.count(Target.id).label('total'),
            func.sum(case((Target.status == TargetStatusEnum.PENDING, 0), else_=0)).label('pending'),
            func.sum(case((Target.status == TargetStatusEnum.APPROVED, 0), else_=0)).label('approved'),
            func.sum(case((Target.status == TargetStatusEnum.REJECTED, 0), else_=0)).label('rejected'),
            func.sum(case((Target.status == TargetStatusEnum.CLOSED, 0), else_=0)).label('closed')
        ).where(
            Target.created_at.between(start_date, end_date)
        )
        overall_result = await self.session.execute(overall_stmt)
        overall_stats = overall_result.one()
        
        date_wise_stmt = select(
            cast(Target.created_at, Date).label('date'),
            func.count(Target.id).label('total'),
            func.sum(case((Target.status == TargetStatusEnum.PENDING, 0), else_=0)).label('pending'),
            func.sum(case((Target.status == TargetStatusEnum.APPROVED, 0), else_=0)).label('approved'),
            func.sum(case((Target.status == TargetStatusEnum.REJECTED, 0), else_=0)).label('rejected'),
            func.sum(case((Target.status == TargetStatusEnum.CLOSED, 0), else_=0)).label('closed')
        ).where(
            Target.created_at.between(start_date, end_date)
        ).group_by(
            cast(Target.created_at, Date)
        )
        date_wise_result = await self.session.execute(date_wise_stmt)
        date_wise_query = date_wise_result.all()
        
        date_stats_dict = {
            row.date: TargetDateWiseStats(
                date=row.date,
                total=row.total or 0,
                pending=row.pending or 0,
                approved=row.approved or 0,
                rejected=row.rejected or 0,
                closed=row.closed or 0
            ) for row in date_wise_query
        }
        
        date_list = self._get_date_list(start_date.date(), end_date.date())
        results = [
            date_stats_dict.get(d, TargetDateWiseStats(date=d, total=0))
            for d in date_list
        ]
        
        return TargetDashboard(
            stats=TargetStats(
                total=overall_stats.total or 0,
                pending=overall_stats.pending or 0,
                approved=overall_stats.approved or 0,
                rejected=overall_stats.rejected or 0,
                closed=overall_stats.closed or 0
            ),
            results=results
        )

    

    async def get_dashboard(
        self,
        time_period: TimePeriodEnum | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        modules: List[str] | None = None
    ) -> DashboardResponse:
        """Get complete dashboard data"""
        
        # Get date range
        
        if time_period:
            date_start, date_end = get_date_range(time_period, start_date, end_date)
        
        elif start_date and end_date:
            date_start, date_end = start_date, end_date
        
        else:
            today = date.today()
            date_start = today.replace(day=1)
            date_end = today
        
        # Convert to datetime
        datetime_start = datetime.combine(date_start, datetime.min.time())
        datetime_end = datetime.combine(date_end, datetime.max.time())
        dashboard_data = {}
        filter_info = {}
        if time_period:
            filter_info = {
                "filter_type": "time_period",
                "value": str(time_period),
                "start_date": date_start,
                "end_date": date_end
            }
        elif start_date and end_date:
            filter_info = {
                "filter_type": "date_range",
                "start_date": date_start,
                "end_date": date_end
            }
        else:
            filter_info = {
                "filter_type": "default_month",
                "start_date": date_start,
                "end_date": date_end
            }
        if not modules or "customers" in modules:
            dashboard_data["customers"] = await self._get_customer_stats(datetime_start, datetime_end)
        if not modules or "vendors" in modules:
            dashboard_data["vendors"] = await self._get_vendor_stats(datetime_start, datetime_end)
        if not modules or "vendor_registrations" in modules:
            dashboard_data["vendor_registrations"] = await self._get_vendor_registration_stats(datetime_start, datetime_end)
        if not modules or "complaints" in modules:
            dashboard_data["complaints"] = await self._get_complaint_stats(datetime_start, datetime_end)
        if not modules or "targets" in modules:
            dashboard_data["targets"] = await self._get_target_stats(datetime_start, datetime_end)
        if not modules or "trips" in modules:
            dashboard_data["trips"] = await self._get_trip_stats(datetime_start, datetime_end)
        
        return {
            "filter_info": filter_info,
            "dashboard_data": dashboard_data
        }
