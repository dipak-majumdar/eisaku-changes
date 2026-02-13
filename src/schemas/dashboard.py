from pydantic import BaseModel
from datetime import date
from typing import Any, Dict, List, Optional


# ============= CUSTOMER STATS =============
class CustomerDateWiseStats(BaseModel):
    date: date
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class CustomerStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class CustomerDashboard(BaseModel):
    stats: CustomerStats
    results: List[CustomerDateWiseStats]


# ============= VENDOR STATS =============
class VendorDateWiseStats(BaseModel):
    date: date
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    active: int = 0
    inactive: int = 0


class VendorStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    active: int = 0
    inactive: int = 0


class VendorDashboard(BaseModel):
    stats: VendorStats
    results: List[VendorDateWiseStats]


# ============= VENDOR REGISTRATION STATS =============
class VendorRegistrationDateWiseStats(BaseModel):
    date: date
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class VendorRegistrationStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class VendorRegistrationDashboard(BaseModel):
    stats: VendorRegistrationStats
    results: List[VendorRegistrationDateWiseStats]


# ============= COMPLAINT STATS =============
class ComplaintDateWiseStats(BaseModel):
    date: date
    total: int = 0
    open: int = 0
    inprogress: int = 0
    closed: int = 0


class ComplaintStats(BaseModel):
    total: int = 0
    open: int = 0
    inprogress: int = 0
    closed: int = 0


class ComplaintDashboard(BaseModel):
    stats: ComplaintStats
    results: List[ComplaintDateWiseStats]


# ============= TARGET STATS =============
class TargetDateWiseStats(BaseModel):
    date: date
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    closed: int = 0


class TargetStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    closed: int = 0


class TargetDashboard(BaseModel):
    stats: TargetStats
    results: List[TargetDateWiseStats]


# ============= TRIP STATS =============
class TripDateWiseStats(BaseModel):
    date: date
    total: int = 0
    pending: int = 0
    in_transit: int = 0
    completed: int = 0
    
    approved: int = 0
    rejected: int = 0


class TripStats(BaseModel):
    total: int = 0
    pending: int = 0
    in_transit: int = 0
    completed: int = 0
   
    approved: int = 0
    rejected: int = 0


class TripDashboard(BaseModel):
    stats: TripStats
    results: List[TripDateWiseStats]


# ============= MAIN DASHBOARD RESPONSE =============
class DashboardData(BaseModel):
    customers: Optional[CustomerDashboard] = None
    vendors: Optional[VendorDashboard] = None
    vendor_registrations: Optional[VendorRegistrationDashboard] = None
    complaints: Optional[ComplaintDashboard] = None
    targets: Optional[TargetDashboard] = None
    trips: Optional[TripDashboard] = None


class DashboardResponse(BaseModel):
    filter_info: Dict[str, Any] 
    dashboard_data: DashboardData