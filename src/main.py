from api.routers import websocket
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
import os
from core.config import TOKEN_URL, TITLE, VERSION
from core.cors import setup_cors
from middlewares.auth import AuthMiddleware

from api.routers import *


app = FastAPI(title=TITLE, version=VERSION)
# Attach custom OpenAPI
app.openapi = lambda: custom_openapi(app)

setup_cors(app)

# Register middleware
app.add_middleware(AuthMiddleware)


@app.on_event("startup")
def on_startup():
    pass


def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=TITLE,
        version=VERSION,
        routes=app.routes,
    )
    
    # OAuth2 Password Flow
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": TOKEN_URL,
                    "scopes": {}
                }
            }
        }
    }

    # ✅ Apply security globally (all endpoints will require it by default)
    openapi_schema["security"] = [{"OAuth2PasswordBearer": []}]

    # 📌 Explicitly define request body schema for login endpoint
    for path, methods in openapi_schema["paths"].items():
        if path == TOKEN_URL and "post" in methods:
            methods["post"]["requestBody"] = {
                "content": {
                    "application/x-www-form-urlencoded": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "identifier": {"type": "string"},
                                "password": {"type": "string"},
                                "login_method": {
                                    "type": "string",
                                    "enum": ["mobile", "email", "username"]
                                },
                                "scope": {"type": "string"},
                                "client_id": {"type": "string"},
                                "client_secret": {"type": "string"},
                            },
                            "required": ["identifier", "password", "login_method"],
                        }
                    }
                },
                "required": True,
            }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.include_router(auth_router, prefix="/api/v1/accounts", tags=["Accounts"])
app.include_router(region_router, prefix="/api/v1/regions", tags=["Regions"])
app.include_router(country_router, prefix="/api/v1/countries", tags=["Countries"])
app.include_router(state_router, prefix="/api/v1/states", tags=["States"])
app.include_router(district_router, prefix="/api/v1/districts", tags=["Districts"])
app.include_router(city_router, prefix="/api/v1/cities", tags=["Cities"])
app.include_router(permission_router, prefix="/api/v1/permissions", tags=["Permissions"])
app.include_router(role_router, prefix="/api/v1/roles", tags=["Roles"])
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(notification_router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(branch_router, prefix="/api/v1/branches", tags=["Branches"])
app.include_router(employee_router, prefix="/api/v1/employees", tags=["Employees"])
app.include_router(vehicle_type_router, prefix="/api/v1/vehicle-types", tags=["Vehicle Types"])
app.include_router(vendor_registration_router, prefix="/api/v1/vendor-registration", tags=["Vendor Registrations"])
app.include_router(vendor_router, prefix="/api/v1/vendors", tags=["Vendors"])
app.include_router(conta, prefix="/api/v1/contact-persons", tags=["Vendor Contact Persons"])
app.include_router(vendor_agreement_router, prefix="/api/v1/agreements", tags=["Vendor Agreements"])
app.include_router(customer_router, prefix="/api/v1/customers", tags=["Customers"])
app.include_router(customer_contact_person_router, prefix="/api/v1/customer-contact-persons", tags=["Customer Contact Persons"]),
app.include_router(customer_agreement_router, prefix="/api/v1/customer-agreements", tags=["Customer Agreements"])

app.include_router(trip_router, prefix="/api/v1/trips", tags=["Trips"])
app.include_router(trip_function_router, prefix="/api/v1/trips", tags=["Trips function"])
app.include_router(advance_payment_router, prefix="/api/v1/advance-payments", tags=["Advance Payments"])

app.include_router(complaint_router, prefix="/api/v1/complaints", tags=["Complaints"])
app.include_router(target_router, prefix="/api/v1/targets", tags=["Targets"])
app.include_router(email_router, prefix="/api/v1/emails", tags=["Emails"])

app.include_router(websocket.router, prefix="/api/v1/ws", tags=["websocket"])


os.makedirs("uploads", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mount the static directory to serve images, including the company logo
app.mount("/static", StaticFiles(directory="src/static"), name="static")