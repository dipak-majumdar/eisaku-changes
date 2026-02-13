from datetime import date as date_type

from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query

from core.security import permission_required
from api.deps import get_dashboard_service, get_target_service, get_trip_service
from models.enums import TimePeriodEnum
from models.trip import TripStatusEnum
from schemas.target import BranchPerformanceList
from services import DashboardService,TripService,TargetService
from schemas.dashboard import DashboardResponse
from schemas.trip import (
    PendingPODTripList,
    TripList as ListSchema,
   
)


VIEW_PERMISSION = 'dashboard.can_view'

router = APIRouter()


@router.get("/", response_model=DashboardResponse)
@permission_required()
async def get_dashboard(
    request: Request,
    time_period: TimePeriodEnum | None = Query(None, description="Filter by time period"),
    start_date: Optional[date] = Query(None, description="Start date for custom range"),
    end_date: Optional[date] = Query(None, description="End date for custom range"),
    modules: Optional[list[str]] = Query(None, description="Comma-separated list of dashboard modules to include"),
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    ... (same docstring as before, add that modules filter is supported) ...
    - modules: Comma-separated values like customers,vendors,vendor_registrations,complaints,trips,targets,etc.
    """
    return await service.get_dashboard(time_period, start_date, end_date, modules)




# LIST TRIPS BY PRIORITY (Today > Future > Past)
@router.get("/trip/priority/", response_model=ListSchema)
@permission_required()
async def list_trips_by_priority(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    time_period: TimePeriodEnum | None = None, 
    start_date: Optional[date] = Query(
        None,
        description="Start date for filtering (format: YYYY-MM-DD, example: 2025-01-01)",
        example=""
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date for filtering (format: YYYY-MM-DD, example: 2025-12-31)",
        example=""
    ), 
    trip_status: Optional[TripStatusEnum] = None,
    service: TripService = Depends(get_trip_service),
):
    """
    List trips with priority ordering:
    - Today's trips first
    - Future trips second
    - Past trips last
    """
    return await service.list_by_trip_date_priority(
        request, page=page, size=size, search=search,
        customer_id=customer_id, time_period=time_period, 
        start_date=start_date, end_date=end_date, trip_status=trip_status
    )
    
    
# LIST TRIPS EXCLUDING POD_SUBMITTED STATUS
@router.get("/pending-pod/", response_model=PendingPODTripList)
@permission_required()
async def list_pending_pod_trips(
    request: Request,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    time_period: TimePeriodEnum | None = None, 
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"), 
    trip_status: Optional[TripStatusEnum] = None,
    service: TripService = Depends(get_trip_service),
):
    """
    List trips pending POD submission with penalty tracking:
    - vehicle_unloaded_date: Date vehicle was unloaded
    - pod_submission_last_date: 18 days from unloading
    - pod_overdue_days: Days late if submitted after last date
    - pod_penalty_amount: ₹100 per overdue day
    """
    return await service.list_pending_pod_trips(
        request, page=page, size=size, search=search,
        customer_id=customer_id, time_period=time_period, 
        start_date=start_date, end_date=end_date, trip_status=trip_status
    )
    
    
    # GET BRANCH PERFORMANCE

# GET BRANCH PERFORMANCE WITH DATE FILTERS
@router.get("/performance/", response_model=BranchPerformanceList)
@permission_required()
async def get_branch_performance(
    request: Request,
    branch_id: Optional[UUID] = Query(None, description="Filter by specific branch"),
    time_period: TimePeriodEnum | None = Query(None, description="Filter by time period (TODAY, THIS_WEEK, THIS_MONTH, etc.)"),
    start_date: Optional[date_type] = Query(
        None,
        description="Start date for filtering (format: YYYY-MM-DD, example: 2025-01-01)",
        example=""
    ),
    end_date: Optional[date_type] = Query(
        None,
        description="End date for filtering (format: YYYY-MM-DD, example: 2025-12-31)",
        example=""
    ),
    service: TargetService = Depends(get_target_service),
):
    """
    Get branch-wise performance metrics with date filtering:
    - Total trips vs achieved trips
    - Total revenue vs achieved revenue
    - Total margin vs achieved margin
    
    Filters:
    - time_period: Predefined periods (TODAY, THIS_WEEK, THIS_MONTH, etc.)
    - start_date & end_date: Custom date range
    - branch_id: Specific branch (ignored for Branch Managers)
    
    Branch Managers see only their branch performance.
    Admins/Management can see all branches or filter by branch_id.
    """
    return await service.get_branch_performance(request, branch_id, time_period, start_date, end_date)
