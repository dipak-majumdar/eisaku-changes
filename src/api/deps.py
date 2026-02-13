
from http.client import HTTPException
from fastapi import Request
from sqlmodel import Session
from fastapi import Depends

from db.session import get_session
from services import *

import functools
import inspect
from fastapi import HTTPException as FastAPIHTTPException

from services import ComplaintService
from services.notifications import NotificationService


# -------------------------------
# Service Dependencies
# -------------------------------
def get_role_service(session: Session = Depends(get_session)) -> RoleService:
    """
    Provides a Role service instance.
    """
    return RoleService(session)


def get_user_service(session: Session = Depends(get_session)) -> UserService:
    """
    Provides a User service instance.
    """
    return UserService(session)


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """
    Provides a Auth service instance.
    """
    return AuthService(session)


def get_country_service(session: Session = Depends(get_session)) -> CountryService:
    """
    Provides a Country service instance.
    """
    return CountryService(session)



def get_state_service(session: Session = Depends(get_session)) -> StateService:
    """
    Provides a State service instance.
    """
    return StateService(session)


def get_district_service(session: Session = Depends(get_session)) -> DistrictService:
    """
    Provides a District service instance.
    """
    return DistrictService(session)


def get_city_service(session: Session = Depends(get_session)) -> CityService:
    """
    Provides a City service instance.
    """
    return CityService(session)



def get_permission_service(session: Session = Depends(get_session)) -> PermissionService:
    """
    Provides a Permission service instance.
    """
    return PermissionService(session)

def get_branch_service(session: Session = Depends(get_session)) -> BranchService:
    """
    Provides a Branch service instance.
    """
    return BranchService(session)

def get_employee_service(session: Session = Depends(get_session)) -> EmployeeService:
    """
    Provides an Employee service instance.
    """
    return EmployeeService(session)

def get_vehicle_type_service(session: Session = Depends(get_session)) -> VehicleTypeService:
    """
    Provides a Vehicle Type service instance.
    """
    return VehicleTypeService(session)

def get_region_service(session: Session = Depends(get_session)) -> RegionService:
    """
    Provides an Region service instance.
    """
    return RegionService(session)

def get_vendor_registration_service(session: Session = Depends(get_session)) -> VendorResistrationService:
    """
    Provides an Region service instance.
    """
    return VendorResistrationService(session)

def get_vendor_service(session: Session = Depends(get_session)) -> VendorService:
    """
    Provides a Vendor service instance.
    """
    return VendorService(session)

def get_vendor_agreement_service(session: Session = Depends(get_session)) -> VendorAgreementService:
    """
    Provides a Vendor service instance.
    """
    return VendorAgreementService(session)


def get_vendor_contact_person_service(session: Session = Depends(get_session)) -> ContactPersonService:
    """
    Provides a Vendor service instance.
    """
    return ContactPersonService(session)

def get_customer_service(session: Session = Depends(get_session)) -> CustomerService:
    """
    Provides a Customer service instance.
    """
    return CustomerService(session)



def get_trip_service(session: Session = Depends(get_session)) -> TripService:
    return TripService(session)

def get_email_service(session: Session = Depends(get_session)) -> EmailService:
    return EmailService(session)

def get_customer_contact(session: Session = Depends(get_session)) -> CustomerContactPersonService:
    return CustomerContactPersonService(session)

def get_customer_agreement(session: Session = Depends(get_session)) -> CustomerAgreementService:
    return CustomerAgreementService(session)

def get_advance_payment_service(session: Session = Depends(get_session)) -> AdvancePaymentService:
    return AdvancePaymentService(session)



def get_complaint_service(session: Session = Depends(get_session)) -> ComplaintService:
    return ComplaintService(session)


def get_target_service(session: Session = Depends(get_session)) -> TargetService:
    return TargetService(session)



# api/deps.py

def get_dashboard_service(session: Session = Depends(get_session)) -> DashboardService:
    return DashboardService(session)


def get_notification_service(session: Session = Depends(get_session)) -> NotificationService:
    return NotificationService(session)
