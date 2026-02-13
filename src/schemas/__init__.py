from .role import RoleCreate, RoleUpdate, RoleRead, RoleList, RolePermissionRead
#from .user import UserCreate, UserUpdate, UserRead, UserList, UserReadWithRole, UserMinimal, UserMinimalList
from .user import UserCreate, UserUpdate, UserRead, UserReadWithRole, UserMinimal, UserMinimalList
from .permission import PermissionCreate, PermissionUpdate, PermissionRead, PermissionList, PermissionReadWithRequired
from .permission import PermissionRead, PermissionReadWithRequired
from .country import CountryCreate, CountryUpdate, CountryRead, CountryList
from .state import StateCreate, StateUpdate, StateRead, StateList
from .district import DistrictCreate, DistrictUpdate, DistrictRead, DistrictList
from .city import CityCreate, CityUpdate, CityRead, CityList
from .branch import BranchCreate, BranchUpdate, BranchRead, BranchList,IdName
from .employee import EmployeeCreate, EmployeeUpdate, EmployeeRead, EmployeeList
from .vehicle_type import VehicleTypeCreate, VehicleTypeUpdate, VehicleTypeRead, VehicleTypeList
from .region import RegionCreate, RegionUpdate, RegionRead, RegionList
from .vendor_resigtration import VendorRegistrationCreate, VendorRegistrationUpdate, VendorRegistrationRead, VendorRegistrationList
from .vendor_agreement import VendorAgreementCreate, VendorAgreementUpdate, VendorAgreementRead,VendorAgreementList
from .vendor import VendorCreate, VendorUpdate, VendorRead, VendorList, VendorDetails, VendorStatusUpdate
from .customer import CustomerCreate, CustomerUpdate, CustomerRead, CustomerList, CustomerDetails, CustomerStatusUpdate
from .contact_person import ContactPersonCreate, ContactPersonUpdate, ContactPersonRead, ContactPersonList
from .trip import TripCreate, TripUpdate, TripRead, TripList
from .customer_contact_person import CustomerContactPersonCreate, CustomerContactPersonUpdate, CustomerContactPersonRead, CustomerContactPersonList
from .customer_agreement import CustomerAgreementCreate, CustomerAgreementUpdate, CustomerAgreementRead, CustomerAgreementList
from .advance_payment import AdvancePaymentCreate, AdvancePaymentUpdate, AdvancePaymentRead, AdvancePaymentList
from .complaint import ComplaintCreate, ComplaintUpdate, ComplaintRead, ComplaintList
from .target import TargetCreate, TargetUpdate, TargetRead, TargetList, TargetStatusUpdate, TargetDetail
from .dashboard import  DashboardData, DashboardResponse, CustomerDateWiseStats, CustomerDashboard, VendorDateWiseStats,VendorDashboard,VendorRegistrationDateWiseStats,VendorRegistrationDashboard,ComplaintDateWiseStats,ComplaintDashboard,TargetDateWiseStats,TargetDashboard,TripDateWiseStats,TripDashboard




__all__ = [
    'RoleCreate', 'RoleUpdate', 'RoleRead', 'RoleList', 'RolePermissionRead',
    'UserCreate', 'UserUpdate', 'UserRead', 'UserReadWithRole', 'UserMinimal', 'UserMinimalList',
    'PermissionCreate', 'PermissionUpdate', 'PermissionRead', 'PermissionList', 'PermissionReadWithRequired',
    'CountryCreate', 'CountryUpdate', 'CountryRead', 'CountryList',
    'StateCreate', 'StateUpdate', 'StateRead', 'StateList',
    'DistrictCreate', 'DistrictUpdate', 'DistrictRead', 'DistrictList',
    'CityCreate', 'CityUpdate', 'CityRead', 'CityList',
    'BranchCreate', 'BranchUpdate', 'BranchRead', 'BranchList',
    'EmployeeCreate', 'EmployeeUpdate', 'EmployeeRead', 'EmployeeList',
    'VehicleTypeCreate', 'VehicleTypeUpdate', 'VehicleTypeRead', 'VehicleTypeList'
    'RegionCreate', 'RegionUpdate', 'RegionRead', 'RegionList',
    'VendorRegistrationCreate', 'VendorRegistrationUpdate', 'VendorRegistrationRead', 'VendorRegistrationList',
    'VendorAgreementCreate', 'VendorAgreementUpdate', 'VendorAgreementRead', 'VendorAgreementList',
    'ContactPersonCreate', 'ContactPersonUpdate', 'ContactPersonRead', 'ContactPersonList',
    'VendorCreate', 'VendorUpdate', 'VendorRead', 'VendorList', 'VendorDetails', 'VendorStatusUpdate',
    'CustomerCreate', 'CustomerUpdate', 'CustomerRead', 'CustomerList', 'CustomerDetails', 'CustomerStatusUpdate',
    'TripCreate', 'TripUpdate', 'TripRead', 'TripList',
    'CustomerContactPersonCreate', 'CustomerContactPersonUpdate', 'CustomerContactPersonRead', 'CustomerContactPersonList',
    'CustomerAgreementCreate', 'CustomerAgreementUpdate', 'CustomerAgreementRead', 'CustomerAgreementList',
    'AdvancePaymentCreate', 'AdvancePaymentUpdate', 'AdvancePaymentRead', 'AdvancePaymentList',
    'ComplaintCreate', 'ComplaintUpdate', 'ComplaintRead', 'ComplaintList',
    'TargetCreate', 'TargetUpdate', 'TargetRead', 'TargetList', 'TargetStatusUpdate', 'TargetDetail',
    'DashboardData', 'DashboardResponse', 'CustomerDateWiseStats', 'CustomerDashboard', 'VendorDateWiseStats', 'VendorDashboard', 'VendorRegistrationDateWiseStats', 'VendorRegistrationDashboard',
    'ComplaintDateWiseStats', 'ComplaintDashboard', 'TargetDateWiseStats', 'TargetDashboard', 'TripDateWiseStats', 'TripDashboard'

]
