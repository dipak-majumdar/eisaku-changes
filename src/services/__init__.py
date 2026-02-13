from .role import Service as RoleService
from .user import Service as UserService
from .auth import Service as AuthService
from .permission import Service as PermissionService
from .country import Service as CountryService
from .state import Service as StateService
from .city import Service as CityService
from .district import Service as DistrictService
from .branch import Service as BranchService
from .employee import Service as EmployeeService
from .vehicle_type import Service as VehicleTypeService
from .region import Service as RegionService
from .vendor_registration import Service as VendorResistrationService
from .vendor import VendorService
from .vendor_agreement import Service as VendorAgreementService
from .contact_person import Service as ContactPersonService
from .customer import Service as CustomerService
from .trip import Service as TripService
from .customer_contact_person import Service as CustomerContactPersonService
from .customer_agreement import Service as CustomerAgreementService
from .advance_payment import Service as AdvancePaymentService
from .complaint import Service as ComplaintService
from .target import Service as TargetService
from .dashboard import Service as DashboardService
from .email import Service as EmailService
from .notifications import NotificationService








__all__ = [
    'RoleService', 'UserService', 'AuthService', 'PermissionService', 'CountryService', 'StateService', 'CityService', 'DistrictService', 'BranchService', 'EmployeeService', 'VehicleTypeService', 'RegionService', 'VendorResistrationService', 'VendorService',
    'VendorAgreementService', 'ContactPersonService', 'CustomerService', 'TripService', 'CustomerContactPersonService', 'CustomerAgreementService', 'AdvancePaymentService', 'ComplaintService', 'TargetService', 'DashboardService', 'EmailService', 'NotificationService'
]

