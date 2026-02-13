# Eisaku TMS API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints (except login) require Bearer token authentication.

### Login
```http
POST /api/v1/accounts/login
Content-Type: application/x-www-form-urlencoded

identifier=your_email_or_mobile&password=your_password&login_method=email
```

### Get Current User
```http
GET /api/v1/accounts/me
Authorization: Bearer {token}
```

## API Endpoints

### Users Management
- `GET /api/v1/users/` - List users (paginated)
- `GET /api/v1/users/minimal` - List users (minimal data, fast)
- `GET /api/v1/users/check-exists` - Check if user exists by email/mobile
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/{user_id}` - Get user by ID
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user
- `PATCH /api/v1/users/{user_id}/status` - Toggle user status

### Customers Management
- `GET /api/v1/customers/` - List customers (paginated)
- `POST /api/v1/customers/` - Create customer
- `GET /api/v1/customers/{customer_id}` - Get customer by ID
- `PUT /api/v1/customers/{customer_id}` - Update customer
- `DELETE /api/v1/customers/{customer_id}` - Delete customer

### Vendors Management
- `GET /api/v1/vendors/` - List vendors (paginated)
- `GET /api/v1/vendors/open-vendors` - List open vendors
- `GET /api/v1/vendors/check-duplicate/` - Check duplicate vendor by GST/PAN
- `GET /api/v1/vendors/{vendor_id}/` - Get vendor by ID
- `POST /api/v1/vendors/` - Create vendor
- `PATCH /api/v1/vendors/{id}/` - Update vendor
- `PATCH /api/v1/vendors/{id}/status/` - Update vendor status
- `PATCH /api/v1/vendors/{id}/credit-period/` - Update vendor credit period
- `PATCH /api/v1/vendors/{id}/bank-details/` - Update vendor bank details
- `DELETE /api/v1/vendors/{id}/` - Delete vendor

### Geography Management

#### Regions
- `GET /api/v1/regions/` - List regions (paginated)
- `POST /api/v1/regions/` - Create region
- `GET /api/v1/regions/{region_id}` - Get region by ID
- `PUT /api/v1/regions/{region_id}` - Update region
- `DELETE /api/v1/regions/{region_id}` - Delete region

#### Countries
- `GET /api/v1/countries/` - List countries (paginated)
- `POST /api/v1/countries/` - Create country
- `GET /api/v1/countries/{country_id}` - Get country by ID
- `PUT /api/v1/countries/{country_id}` - Update country
- `DELETE /api/v1/countries/{country_id}` - Delete country

#### States
- `GET /api/v1/states/` - List states (paginated)
- `POST /api/v1/states/` - Create state
- `GET /api/v1/states/{state_id}` - Get state by ID
- `PUT /api/v1/states/{state_id}` - Update state
- `DELETE /api/v1/states/{state_id}` - Delete state

#### Districts
- `GET /api/v1/districts/` - List districts (paginated)
- `POST /api/v1/districts/` - Create district
- `GET /api/v1/districts/{district_id}` - Get district by ID
- `PUT /api/v1/districts/{district_id}` - Update district
- `DELETE /api/v1/districts/{district_id}` - Delete district

#### Cities
- `GET /api/v1/cities/` - List cities (paginated)
- `POST /api/v1/cities/` - Create city
- `GET /api/v1/cities/{city_id}` - Get city by ID
- `PUT /api/v1/cities/{city_id}` - Update city
- `DELETE /api/v1/cities/{city_id}` - Delete city

### Roles & Permissions

#### Roles
- `GET /api/v1/roles/` - List roles (paginated)
- `POST /api/v1/roles/` - Create role
- `GET /api/v1/roles/{role_id}` - Get role by ID
- `PUT /api/v1/roles/{role_id}` - Update role
- `DELETE /api/v1/roles/{role_id}` - Delete role

#### Permissions
- `GET /api/v1/permissions/` - List permissions (paginated)
- `POST /api/v1/permissions/` - Create permission
- `GET /api/v1/permissions/{permission_id}` - Get permission by ID
- `PUT /api/v1/permissions/{permission_id}` - Update permission
- `DELETE /api/v1/permissions/{permission_id}` - Delete permission

### Branches & Employees

#### Branches
- `GET /api/v1/branches/` - List branches (paginated)
- `POST /api/v1/branches/` - Create branch
- `GET /api/v1/branches/{branch_id}` - Get branch by ID
- `PUT /api/v1/branches/{branch_id}` - Update branch
- `DELETE /api/v1/branches/{branch_id}` - Delete branch

#### Employees
- `GET /api/v1/employees/` - List employees (paginated)
- `POST /api/v1/employees/` - Create employee
- `GET /api/v1/employees/{employee_id}` - Get employee by ID
- `PUT /api/v1/employees/{employee_id}` - Update employee
- `DELETE /api/v1/employees/{employee_id}` - Delete employee

### Vehicle Types
- `GET /api/v1/vehicle-types/` - List vehicle types (paginated)
- `POST /api/v1/vehicle-types/` - Create vehicle type
- `GET /api/v1/vehicle-types/{vehicle_type_id}` - Get vehicle type by ID
- `PUT /api/v1/vehicle-types/{vehicle_type_id}` - Update vehicle type
- `DELETE /api/v1/vehicle-types/{vehicle_type_id}` - Delete vehicle type

### Vendor Registration
- `GET /api/v1/vendor-registration/` - List vendor registrations (paginated)
- `POST /api/v1/vendor-registration/` - Create vendor registration
- `GET /api/v1/vendor-registration/{id}` - Get vendor registration by ID
- `PUT /api/v1/vendor-registration/{id}` - Update vendor registration
- `PATCH /api/v1/vendor-registration/{id}/status` - Update vendor registration status
- `DELETE /api/v1/vendor-registration/{id}` - Delete vendor registration
- `POST /api/v1/vendor-registration/check-duplicate-gst-pan/` - Check duplicate GST/PAN

### Agreements

#### Vendor Agreements
- `GET /api/v1/agreements/` - List vendor agreements (paginated)
- `POST /api/v1/agreements/` - Create vendor agreement
- `GET /api/v1/agreements/{agreement_id}` - Get vendor agreement by ID
- `PUT /api/v1/agreements/{agreement_id}` - Update vendor agreement
- `DELETE /api/v1/agreements/{agreement_id}` - Delete vendor agreement
- `PATCH /api/v1/agreements/{agreement_id}/status` - Toggle agreement status

#### Customer Agreements
- `GET /api/v1/customer-agreements/` - List customer agreements (paginated)
- `POST /api/v1/customer-agreements/` - Create customer agreement
- `GET /api/v1/customer-agreements/{agreement_id}` - Get customer agreement by ID
- `PUT /api/v1/customer-agreements/{agreement_id}` - Update customer agreement
- `DELETE /api/v1/customer-agreements/{agreement_id}` - Delete customer agreement

### Contact Persons

#### Vendor Contact Persons
- `GET /api/v1/contact-persons/` - List vendor contact persons (paginated)
- `POST /api/v1/contact-persons/` - Create vendor contact person
- `GET /api/v1/contact-persons/{contact_id}` - Get vendor contact person by ID
- `PUT /api/v1/contact-persons/{contact_id}` - Update vendor contact person
- `DELETE /api/v1/contact-persons/{contact_id}` - Delete vendor contact person

#### Customer Contact Persons
- `GET /api/v1/customer-contact-persons/` - List customer contact persons (paginated)
- `POST /api/v1/customer-contact-persons/` - Create customer contact person
- `GET /api/v1/customer-contact-persons/{contact_id}` - Get customer contact person by ID
- `PUT /api/v1/customer-contact-persons/{contact_id}` - Update customer contact person
- `DELETE /api/v1/customer-contact-persons/{contact_id}` - Delete customer contact person

### Trips Management
- `GET /api/v1/trips/` - List trips (paginated)
- `POST /api/v1/trips/` - Create trip
- `GET /api/v1/trips/{trip_id}` - Get trip by ID
- `PUT /api/v1/trips/{trip_id}` - Update trip
- `DELETE /api/v1/trips/{trip_id}` - Delete trip

### Advance Payments
- `GET /api/v1/advance-payments/` - List advance payments (paginated)
- `POST /api/v1/advance-payments/` - Create advance payment
- `GET /api/v1/advance-payments/{payment_id}` - Get advance payment by ID
- `PUT /api/v1/advance-payments/{payment_id}` - Update advance payment
- `DELETE /api/v1/advance-payments/{payment_id}` - Delete advance payment

### Complaints
- `GET /api/v1/complaints/` - List complaints (paginated)
- `POST /api/v1/complaints/` - Create complaint
- `GET /api/v1/complaints/{complaint_id}` - Get complaint by ID
- `PUT /api/v1/complaints/{complaint_id}` - Update complaint
- `DELETE /api/v1/complaints/{complaint_id}` - Delete complaint

### Targets
- `GET /api/v1/targets/` - List targets (paginated)
- `POST /api/v1/targets/` - Create target
- `GET /api/v1/targets/{target_id}` - Get target by ID
- `PUT /api/v1/targets/{target_id}` - Update target
- `DELETE /api/v1/targets/{target_id}` - Delete target

### Emails
- `GET /api/v1/emails/` - List emails (paginated)
- `POST /api/v1/emails/` - Send email
- `GET /api/v1/emails/{email_id}` - Get email by ID

### Dashboard
- `GET /api/v1/dashboard/` - Get dashboard statistics

### Notifications
- `GET /api/v1/notifications/` - List notifications (paginated)
- `POST /api/v1/notifications/` - Create notification
- `GET /api/v1/notifications/{notification_id}` - Get notification by ID
- `PUT /api/v1/notifications/{notification_id}` - Update notification
- `DELETE /api/v1/notifications/{notification_id}` - Delete notification

### WebSocket
- `GET /api/v1/ws/info` - Get WebSocket connection information
- `WS /api/v1/ws` - WebSocket endpoint for real-time updates

## Common Query Parameters

### Pagination
- `page` - Page number (default: 1)
- `size` - Items per page (default: 10)

### Search & Filters
- `search` - Search term for text fields
- `role_id` - Filter by role ID
- `country_id` - Filter by country ID
- `state_id` - Filter by state ID
- `district_id` - Filter by district ID
- `city_id` - Filter by city ID
- `start_date` - Filter by start date
- `end_date` - Filter by end date
- `time_period` - Filter by time period (enum values)

## Response Format

### Success Response
```json
{
  "total": 100,
  "next": "http://localhost:8000/api/v1/users/?page=2",
  "previous": null,
  "results": [...]
}
```

### Error Response
```json
{
  "detail": "Error message description"
}
```

## How to Use the Postman Collection

1. Import the `TMS_API_Postman_Collection.json` file into Postman
2. Set the `base_url` variable to your API server URL
3. First, use the Login endpoint to get an authentication token
4. Copy the token and set it as the `auth_token` variable
5. All other requests will automatically include the Bearer token

## Notes

- All datetime fields should be in ISO 8601 format
- UUID fields should be valid UUID strings
- File uploads use multipart/form-data format
- Some endpoints may require additional permissions based on user roles
