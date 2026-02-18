from sqlalchemy.sql.functions import user
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session
from uuid import UUID

from core.config import (
    EMAIL_PASSWORD,
    EMAIL_ID,
    EMAIL_PORT,
    EMAIL_SERVICE,
    EMAIL_FROM_NAME,
) 
from models import User, Email
from datetime import datetime
from pathlib import Path
from services.helper import get_branch_manager_id, administrative_user_id


conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL_ID,
    MAIL_PASSWORD=EMAIL_PASSWORD,
    MAIL_FROM=EMAIL_ID,
    MAIL_PORT=EMAIL_PORT,
    MAIL_SERVER=EMAIL_SERVICE,
    MAIL_FROM_NAME=EMAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates/email",
)


async def send_email(
        session: AsyncSession,
        request: Request, 
        user: User, 
        header_msg: str, 
        body_msg: str,
        recipient_email: str | None = None,  # ✅ Add direct email
        recipient_name: str | None = None,   # ✅ Add direct name
        ): 
    email = recipient_email if recipient_email else (user.email if user else None)
    name = recipient_name if recipient_name else (user.name if user else "User")
    
    if not email:
        raise ValueError("Either user or recipient_email must be provided")
    # Render the HTML body from the template to store it in the database
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(conf.TEMPLATE_FOLDER))
    template = env.get_template("user_email.html")

    template_body = {
        "username": name,
        "body": body_msg,
        "company_name": "Eisaku", 
        "current_year": datetime.now().year,
    }

    html_body = template.render(template_body)

    # Create an email log entry
    email_log = Email(
        subject=header_msg,
        body=body_msg,
        recipient_email= email,
        status="pending",
        created_by=request.state.user.id,
    )
    
    session.add(email_log)
    await session.commit()
    await session.refresh(email_log)

    message = MessageSchema(
        subject=header_msg,
        recipients=[email],
        body=html_body,
        subtype="html",
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        email_log.status = "sent"
    except Exception as e:
        email_log.status = "failed"
    
    session.add(email_log)
    await session.commit()

# async def send_onboarding_email(session: Session,request: Request,user: User):


class EmailNotificationService:
    """
    Production-ready email notification service for event-based emails.
    Supports template-based rendering and multiple recipients per event.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.fm = FastMail(conf)
        
    def _render_template(self, template_name: str, context: dict) -> str:
        """Render Jinja2 template with given context"""
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(conf.TEMPLATE_FOLDER))
        template = env.get_template(template_name)
        return template.render(context)
    
    async def _send_email_to_recipient(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        html_body: str,
        created_by_id: UUID,
        attachments: list[str] | None = None
    ) -> bool:
        """Send email to a single recipient and log to database"""
        try:
            # Create email log entry
            email_log = Email(
                subject=subject,
                body=subject,  # Store subject as body for logging
                recipient_email=recipient_email,
                status="pending",
                created_by=created_by_id,
            )
            
            self.session.add(email_log)
            await self.session.commit()
            await self.session.refresh(email_log)

            # Send email
            message = MessageSchema(
                subject=subject,
                recipients=[recipient_email],
                body=html_body,
                subtype="html",
                attachments=attachments or []
            )

            await self.fm.send_message(message)
            email_log.status = "sent"
            # print(f"✅ Email sent to {recipient_name} ({recipient_email})")
            
        except Exception as e:
            email_log.status = "failed"
            print(f"❌ Failed to send email to {recipient_name} ({recipient_email}): {str(e)}")
            return False
        finally:
            self.session.add(email_log)
            await self.session.commit()
        
        return True
    
    async def send_trip_created_email(
        self,
        trip_id: UUID,
        request: Request
    ) -> None:
        """
        Send trip creation notification emails to customer, manager, and management.
        
        Args:
            trip_id: UUID of the created trip
            request: FastAPI Request object for user context
        """
        from models import Trip, Customer, Employee, User, Role
        from models.trip import TripAddress, AddressTypeEnum
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        from services.helper import get_branch_manager_id, administrative_user_id
        
        try:
            # Fetch trip with all necessary relationships
            stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer).joinedload(Customer.user),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            result = await self.session.execute(stmt)
            trip = result.unique().scalars().first()
            
            if not trip:
                print(f"❌ Trip {trip_id} not found for email notification")
                return
            
            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
            
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
            
            # Prepare base template context
            base_context = {
                "customer_name": trip.customer.customer_name if trip.customer else "Customer",
                "trip_code": trip.trip_code,
                "trip_id": str(trip.id),
                "trip_rate": trip.trip_rate,
                "loading_unloading_charges": trip.loading_unloading_charges,
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name,
                "loading_address": loading_address_str or "N/A",
                "unloading_address": unloading_address_str or "N/A",
                "special_instructions": trip.instructions or "No special instructions",
                "company_name": "Eisaku",
                "current_year": datetime.now().year,
                "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip.id}",
            }
            
            subject = f"Trip Created - {trip.trip_code}"
            
            # 1. Send to Customer
            if trip.customer and trip.customer.user and trip.customer.user.email:
                customer_context = {
                    **base_context,
                    "is_manager": False,
                    "is_admin": False,
                }
                html_body = self._render_template("trip-created.html", customer_context)
                await self._send_email_to_recipient(
                    recipient_email=trip.customer.user.email,
                    recipient_name=trip.customer.customer_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id
                )
            else:
                print(f"⚠️ No customer email found for trip {trip.trip_code}")
            
            # 2. Send to Branch Manager(s)
            manager_ids = await get_branch_manager_id(self.session, trip.branch_id)
            if manager_ids:
                # Convert string IDs to UUIDs
                manager_uuids = [UUID(id_str) for id_str in manager_ids]
                
                # Fetch manager user details
                stmt_managers = (
                    select(User)
                    .join(Employee, Employee.user_id == User.id)
                    .filter(User.id.in_(manager_uuids))
                )
                result_managers = await self.session.execute(stmt_managers)
                managers = result_managers.unique().scalars().all()
                
                for manager in managers:
                    if manager.email:
                        manager_context = {
                            **base_context,
                            "customer_name": manager.name,
                            "is_manager": True,
                            "is_admin": False,
                        }
                        html_body = self._render_template("trip-created.html", manager_context)
                        await self._send_email_to_recipient(
                            recipient_email=manager.email,
                            recipient_name=manager.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id
                        )
            else:
                print(f"⚠️ No branch manager found for branch {trip.branch_id}")
            
            print(f"✅ Trip creation email notifications completed for {trip.trip_code}")
            
        except Exception as e:
            print(f"❌ Error sending trip creation emails: {str(e)}")
            # Don't raise - email failures shouldn't break trip creation

    async def send_trip_approved_email(
        self,
        trip_id: UUID,
        request: Request
    ) -> None:
        """
        Send trip approval notification emails to supervisors.
        
        Args:
            trip_id: UUID of the approved trip
            request: FastAPI Request object for user context
        """
        from models import Trip, Customer, Employee, User, Role
        from models.trip import TripAddress, AddressTypeEnum
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        from services.helper import get_supervisors_in_branch
        from uuid import UUID
        
        try:
            # Fetch trip with all necessary relationships
            stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer).joinedload(Customer.user),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            result = await self.session.execute(stmt)
            trip = result.unique().scalars().first()
            
            if not trip:
                print(f"❌ Trip {trip_id} not found for email notification")
                return
            
            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
            
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
            
            # Prepare base template context
            base_context = {
                "trip_code": trip.trip_code,
                "trip_rate": trip.trip_rate,
                "loading_unloading_charges": trip.loading_unloading_charges,
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name,
                "loading_address": loading_address_str or "N/A",
                "unloading_address": unloading_address_str or "N/A",
                "special_instructions": trip.instructions or "No special instructions",
                "company_name": "Eisaku",
                "current_year": datetime.now().year,
            }
            
            subject = f"Trip Approved - {trip.trip_code}"
            
            # Send to Supervisors
            supervisor_ids = await get_supervisors_in_branch(self.session, trip.branch_id)
            if supervisor_ids:
                # Convert string IDs to UUIDs
                supervisor_uuids = [UUID(id_str) for id_str in supervisor_ids]
                
                # Fetch supervisor user details
                stmt_supervisors = (
                    select(User)
                    .join(Employee, Employee.user_id == User.id)
                    .filter(User.id.in_(supervisor_uuids))
                )
                result_supervisors = await self.session.execute(stmt_supervisors)
                supervisors = result_supervisors.unique().scalars().all()
                
                for supervisor in supervisors:
                    if supervisor.email:
                        supervisor_context = {
                            **base_context,
                            "customer_name": supervisor.name,
                        }
                        html_body = self._render_template("trip-approved.html", supervisor_context)
                        await self._send_email_to_recipient(
                            recipient_email=supervisor.email,
                            recipient_name=supervisor.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id
                        )
                print(f"✅ Trip approval emails sent to {len(supervisors)} supervisors")
            else:
                print(f"⚠️ No supervisors found for branch {trip.branch_id}")
                
        except Exception as e:
            print(f"❌ Error sending trip approval emails: {str(e)}")

    async def send_vendor_assigned_email(
        self,
        trip_id: UUID,
        request: Request
    ) -> None:
        """
        Send vendor assignment notification emails to Customer, Vendor, and Branch Manager.
        
        Args:
            trip_id: UUID of the trip
            request: FastAPI Request object for user context
        """
        from models import Trip, Customer, Vendor, Employee, User, Role
        from models.trip import TripAddress, AddressTypeEnum, TripVendor
        from models.vendor import VendorContactPerson
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        from services.helper import get_branch_manager_id
        from uuid import UUID
        
        try:
            # Fetch trip with all necessary relationships
            stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer).joinedload(Customer.user),
                    joinedload(Trip.customer).selectinload(Customer.contact_persons),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).joinedload(Vendor.user),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).selectinload(Vendor.contact_persons),
                    joinedload(Trip.assigned_vendor).selectinload(TripVendor.drivers),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            result = await self.session.execute(stmt)
            trip = result.unique().scalars().first()
            
            if not trip:
                print(f"❌ Trip {trip_id} not found for vendor assignment email")
                return
                
            if not trip.assigned_vendor:
                 print(f"❌ Trip {trip_id} has no assigned vendor for email notification")
                 return

            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
            
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
            
            # Prepare base template context
            base_context = {
                "trip_code": trip.trip_code,
                "trip_rate": trip.trip_rate, # Customer Rate
                "loading_unloading_charges": trip.loading_unloading_charges,
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name,
                "loading_address": loading_address_str or "N/A",
                "unloading_address": unloading_address_str or "N/A",
                "special_instructions": trip.instructions or "No special instructions",
                "company_name": "Eisaku",
                "current_year": datetime.now().year,
                
                # Vehical Details
                "assigned_vehicle_type": trip.assigned_vendor.vehicle_type.name if trip.assigned_vendor.vehicle_type else "N/A",
                "assigned_vehicle_number": trip.assigned_vendor.vehicle_no or "N/A",
                "assigned_vehicle_capacity": trip.assigned_vendor.tons,
                "assigned_vehicle_insurance_expiry": trip.assigned_vendor.insurance_expiry_date.strftime("%d-%m-%Y") if trip.assigned_vendor.insurance_expiry_date else "N/A",
                
                # Driver Details
                "driver_name": trip.assigned_vendor.drivers[0].driver_name if trip.assigned_vendor.drivers else "N/A",
                "driver_mobile": trip.assigned_vendor.drivers[0].driver_mobile_no if trip.assigned_vendor.drivers else "N/A",
                "driver_license": trip.assigned_vendor.drivers[0].driver_licence_no if trip.assigned_vendor.drivers else "N/A",
                "driver_license_expiry": trip.assigned_vendor.drivers[0].driver_licence_expiry.strftime("%d-%m-%Y") if trip.assigned_vendor.drivers else "N/A",

                # Vendor/Fleet Details (for vendor/manager only)
                "vendor_name": trip.assigned_vendor.vendor.vendor_name,
                "vendor_branch_name": trip.branch.name,
                "vendor_trip_rate": trip.assigned_vendor.trip_rate,
                "vendor_other_charges": trip.assigned_vendor.other_charges + trip.assigned_vendor.other_unloading_charges,
                "vendor_advance": trip.assigned_vendor.advance,

                "start_date": trip.trip_date.strftime("%d-%m-%Y"), # Assuming trip date as start
                
                "web_url": "http://157.173.219.215:3000/market-trip/view/{trip.id}", # Replace with actual base URL
                "trip_id": str(trip.id)
            }
            
            subject = f"Vendor Assigned - {trip.trip_code}"
            
            # 1. Send to Customer
            if trip.customer.user and trip.customer.user.email:
                customer_context = {
                    **base_context,
                    "name": trip.customer.customer_name,
                    "is_customer": True,
                    "is_branch_manager": False,
                    "is_vendor": False
                }
                html_body = self._render_template("vendor-assigned.html", customer_context)
                await self._send_email_to_recipient(
                    recipient_email=trip.customer.user.email,
                    recipient_name=trip.customer.customer_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id
                )
                print(f"✅ Vendor assignment email sent to Customer: {trip.customer.user.email}")

            # 2. Send to Branch Manager
            manager_ids = await get_branch_manager_id(self.session, trip.branch_id)
            if manager_ids:
                manager_uuids = [UUID(id_str) for id_str in manager_ids]
                stmt_managers = (
                    select(User)
                    .join(Employee, Employee.user_id == User.id)
                    .filter(User.id.in_(manager_uuids))
                )
                result_managers = await self.session.execute(stmt_managers)
                managers = result_managers.unique().scalars().all()
                
                for manager in managers:
                    if manager.email:
                        manager_context = {
                            **base_context,
                            "name": manager.name,
                            "is_customer": False,
                            "is_branch_manager": True,
                            "is_vendor": False,
                             "trip_rate": trip.assigned_vendor.trip_rate 
                        }
                        html_body = self._render_template("vendor-assigned.html", manager_context)
                        await self._send_email_to_recipient(
                            recipient_email=manager.email,
                            recipient_name=manager.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id
                        )
                print(f"✅ Vendor assignment emails sent to {len(managers)} Branch Managers")

            # 3. Send to Vendor
            vendor_email = None
            vendor_name = trip.assigned_vendor.vendor.vendor_name
            
            # Try contact persons first
            if trip.assigned_vendor.vendor.contact_persons:
                # Prefer primary contact or first one
                vendor_email = trip.assigned_vendor.vendor.contact_persons[0].email
            
            # Fallback to user email
            if not vendor_email and trip.assigned_vendor.vendor.user:
                vendor_email = trip.assigned_vendor.vendor.user.email
            
            if vendor_email:
                vendor_context = {
                    **base_context,
                    "name": vendor_name,
                    "is_customer": False,
                    "is_branch_manager": False,
                    "is_vendor": True,
                    "trip_rate": trip.assigned_vendor.trip_rate
                }
                html_body = self._render_template("vendor-assigned.html", vendor_context)
                await self._send_email_to_recipient(
                    recipient_email=vendor_email,
                    recipient_name=vendor_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id
                )
                print(f"✅ Vendor assignment email sent to Vendor: {vendor_email}")
            else:
                print(f"⚠️ No email found for Vendor {vendor_name}")

        except Exception as e:
            print(f"❌ Error sending vendor assignment emails: {str(e)}")

    async def send_fleet_rate_approved_email(
        self,
        trip_id: UUID,
        request: Request
    ) -> None:
        """
        Send fleet rate approval notification emails to Supervisor, Branch Manager, Customer, and Vendor.
        
        Args:
            trip_id: UUID of the trip
            request: FastAPI Request object for user context
        """
        from models import Trip, Customer, Vendor, Employee, User, Role
        from models.trip import TripAddress, AddressTypeEnum, TripVendor
        from models.vendor import VendorContactPerson
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        from services.helper import get_branch_manager_id, get_supervisors_in_branch
        from uuid import UUID
        
        try:
            # Fetch trip with all necessary relationships (same as vendor assignment)
            stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer).joinedload(Customer.user),
                    joinedload(Trip.customer).selectinload(Customer.contact_persons),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).joinedload(Vendor.user),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).selectinload(Vendor.contact_persons),
                    joinedload(Trip.assigned_vendor).selectinload(TripVendor.drivers),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            result = await self.session.execute(stmt)
            trip = result.unique().scalars().first()
            
            if not trip:
                print(f"❌ Trip {trip_id} not found for fleet rate approval email")
                return
            
            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
            
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
            
            # Prepare base template context
            base_context = {
                "trip_code": trip.trip_code,
                "trip_rate": trip.trip_rate,
                "loading_unloading_charges": trip.loading_unloading_charges,
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name,
                "loading_details": loading_address_str or "N/A",
                "unloading_details": unloading_address_str or "N/A",
                "instructions_details": trip.instructions or "No special instructions",
                "company_name": "Eisaku",
                "current_year": datetime.now().year,
                
                # Vehical Details
                "assigned_vehicle_type": trip.assigned_vendor.vehicle_type.name if trip.assigned_vendor and trip.assigned_vendor.vehicle_type else "N/A",
                "assigned_vehicle_number": trip.assigned_vendor.vehicle_no if trip.assigned_vendor else "N/A",
                "assigned_vehicle_capacity": trip.assigned_vendor.tons if trip.assigned_vendor else "N/A",
                "assigned_vehicle_insurance_expiry": trip.assigned_vendor.insurance_expiry_date.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.insurance_expiry_date else "N/A",
                
                # Driver Details
                "driver_name": trip.assigned_vendor.drivers[0].driver_name if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_mobile": trip.assigned_vendor.drivers[0].driver_mobile_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_licence": trip.assigned_vendor.drivers[0].driver_licence_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_license_expiry": trip.assigned_vendor.drivers[0].driver_licence_expiry.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",

                # Vendor/Fleet Details
                "vendor_name": trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "N/A",
                "vendor_branch_name": trip.branch.name if trip.branch else "N/A",
                "vendor_trip_rate": trip.assigned_vendor.trip_rate if trip.assigned_vendor else "N/A",
                "vendor_other_charges": (trip.assigned_vendor.other_charges + trip.assigned_vendor.other_unloading_charges) if trip.assigned_vendor else "N/A",
                "vendor_advance": trip.assigned_vendor.advance if trip.assigned_vendor else "N/A",

                "start_date": trip.trip_date.strftime("%d-%m-%Y"),
                 # Web URL not needed for this notification based on template analysis (only for manager action which is not here)
                "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip.id}", 
                "trip_id": str(trip.id)
            }
            
            subject = f"Fleet Rate Approved - {trip.trip_code}"

            # 1. Send to Supervisor
            supervisor_ids = await get_supervisors_in_branch(self.session, trip.branch_id)
            if supervisor_ids:
                supervisor_uuids = [UUID(id_str) for id_str in supervisor_ids]
                stmt_supervisors = (
                    select(User)
                    .join(Employee, Employee.user_id == User.id)
                    .filter(User.id.in_(supervisor_uuids))
                )
                result_supervisors = await self.session.execute(stmt_supervisors)
                supervisors = result_supervisors.unique().scalars().all()
                
                for supervisor in supervisors:
                    if supervisor.email:
                        supervisor_context = {
                            **base_context,
                            "name": supervisor.name,
                            "is_supervisor": True,
                            "is_branch_manager": False,
                            "is_vendor": False,
                            "is_customer": False
                        }
                        html_body = self._render_template("fleet-rate-approval.html", supervisor_context)
                        await self._send_email_to_recipient(
                            recipient_email=supervisor.email,
                            recipient_name=supervisor.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id
                        )
                print(f"✅ Fleet rate approved emails sent to {len(supervisors)} Supervisors")

            # 2. Send to Branch Manager
            manager_ids = await get_branch_manager_id(self.session, trip.branch_id)
            if manager_ids:
                manager_uuids = [UUID(id_str) for id_str in manager_ids]
                stmt_managers = (
                    select(User)
                    .join(Employee, Employee.user_id == User.id)
                    .filter(User.id.in_(manager_uuids))
                )
                result_managers = await self.session.execute(stmt_managers)
                managers = result_managers.unique().scalars().all()
                
                for manager in managers:
                    if manager.email:
                        manager_context = {
                            **base_context,
                            "name": manager.name,
                            "is_supervisor": False,
                            "is_branch_manager": True,
                            "is_vendor": False,
                            "is_customer": False
                        }
                        html_body = self._render_template("fleet-rate-approval.html", manager_context)
                        await self._send_email_to_recipient(
                            recipient_email=manager.email,
                            recipient_name=manager.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id
                        )
                print(f"✅ Fleet rate approved emails sent to {len(managers)} Branch Managers")

            # 3. Send to Customer
            if trip.customer.user and trip.customer.user.email:
                customer_context = {
                    **base_context,
                    "name": trip.customer.customer_name,
                    "is_supervisor": False,
                    "is_branch_manager": False,
                    "is_vendor": False,
                    "is_customer": True
                }
                html_body = self._render_template("fleet-rate-approval.html", customer_context)
                await self._send_email_to_recipient(
                    recipient_email=trip.customer.user.email,
                    recipient_name=trip.customer.customer_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id
                )
                print(f"✅ Fleet rate approved email sent to Customer: {trip.customer.user.email}")

            # 4. Send to Vendor
            vendor_email = None
            vendor_name = trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "Vendor"
            
            if trip.assigned_vendor and trip.assigned_vendor.vendor:
                if trip.assigned_vendor.vendor.contact_persons:
                    vendor_email = trip.assigned_vendor.vendor.contact_persons[0].email
                if not vendor_email and trip.assigned_vendor.vendor.user:
                    vendor_email = trip.assigned_vendor.vendor.user.email
            
            if vendor_email:
                vendor_context = {
                    **base_context,
                    "name": vendor_name,
                    "is_supervisor": False,
                    "is_branch_manager": False,
                    "is_vendor": True,
                    "is_customer": False
                }
                html_body = self._render_template("fleet-rate-approval.html", vendor_context)
                await self._send_email_to_recipient(
                    recipient_email=vendor_email,
                    recipient_name=vendor_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id
                )
                print(f"✅ Fleet rate approved email sent to Vendor: {vendor_email}")

        except Exception as e:
            print(f"❌ Error sending fleet rate approved emails: {str(e)}")

    async def send_vehicle_loaded_email(
        self,
        trip_id: UUID,
        request: Request
    ) -> None:
        """
        Send vehicle loaded notification emails to Management, Vendor, and Customer with attachments.
        
        Args:
            trip_id: UUID of the trip
            request: FastAPI Request object for user context
        """
        from models import Trip, Customer, Vendor, Employee, User, Role
        from models.trip import TripAddress, AddressTypeEnum, TripVendor, TripDocument
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        from services.helper import administrative_user_id
        from uuid import UUID
        import os
        
        try:
            # Fetch trip with all necessary relationships
            stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer).joinedload(Customer.user),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).joinedload(Vendor.user),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).selectinload(Vendor.contact_persons),
                    joinedload(Trip.assigned_vendor).selectinload(TripVendor.drivers),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                    joinedload(Trip.trip_documents)
                )
                .filter(Trip.id == trip_id)
            )
            result = await self.session.execute(stmt)
            trip = result.unique().scalars().first()
            
            if not trip:
                print(f"❌ Trip {trip_id} not found for vehicle loaded email")
                return

            # Prepare Attachments
            attachments = []
            if trip.trip_documents:
                docs = trip.trip_documents
                if docs.eway_bill and os.path.exists(docs.eway_bill):
                    attachments.append(docs.eway_bill)
                if docs.invoice_copy and os.path.exists(docs.invoice_copy):
                    attachments.append(docs.invoice_copy)
                if docs.vehicle_image and os.path.exists(docs.vehicle_image):
                    attachments.append(docs.vehicle_image)
                if docs.lr_copy and os.path.exists(docs.lr_copy):
                    attachments.append(docs.lr_copy)

            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
            
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
            
            # Prepare base template context
            base_context = {
                "trip_code": trip.trip_code,
                "trip_rate": trip.trip_rate,
                "loading_unloading_charges": trip.loading_unloading_charges,
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name,
                "loading_details": loading_address_str or "N/A",
                "unloading_details": unloading_address_str or "N/A",
                "instructions_details": trip.instructions or "No special instructions",
                "company_name": "Eisaku",
                "current_year": datetime.now().year,
                
                # Vehical Details
                "assigned_vehicle_type": trip.assigned_vendor.vehicle_type.name if trip.assigned_vendor and trip.assigned_vendor.vehicle_type else "N/A",
                "assigned_vehicle_number": trip.assigned_vendor.vehicle_no if trip.assigned_vendor else "N/A",
                "assigned_vehicle_capacity": trip.assigned_vendor.tons if trip.assigned_vendor else "N/A",
                "assigned_vehicle_insurance_expiry": trip.assigned_vendor.insurance_expiry_date.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.insurance_expiry_date else "N/A",
                
                # Driver Details
                "driver_name": trip.assigned_vendor.drivers[0].driver_name if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_mobile": trip.assigned_vendor.drivers[0].driver_mobile_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_licence": trip.assigned_vendor.drivers[0].driver_licence_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                "driver_license_expiry": trip.assigned_vendor.drivers[0].driver_licence_expiry.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",

                # Vendor/Fleet Details
                "vendor_name": trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "N/A",
                "vendor_branch_name": trip.branch.name if trip.branch else "N/A",
                "vendor_trip_rate": trip.assigned_vendor.trip_rate if trip.assigned_vendor else "N/A",
                "vendor_other_charges": (trip.assigned_vendor.other_charges + trip.assigned_vendor.other_unloading_charges) if trip.assigned_vendor else "N/A",
                "vendor_advance": trip.assigned_vendor.advance if trip.assigned_vendor else "N/A",

                "start_date": trip.trip_date.strftime("%d-%m-%Y"),
                 # Web URL for management to approve
                "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip.id}", 
                "trip_id": str(trip.id)
            }
            
            subject = f"Vehicle Loaded - {trip.trip_code}"

            # 1. Send to Management
            management_ids = await administrative_user_id(self.session, "management")
            if management_ids:
                management_uuids = [UUID(id_str) for id_str in management_ids]
                stmt_mgmt = select(User).filter(User.id.in_(management_uuids))
                result_mgmt = await self.session.execute(stmt_mgmt)
                managers = result_mgmt.unique().scalars().all()
                
                for manager in managers:
                    if manager.email:
                        mgmt_context = {
                            **base_context,
                            "name": manager.name,
                            "is_management": True,
                            "is_vendor": False,
                            "is_customer": False
                        }
                        html_body = self._render_template("vehicale-loaded.html", mgmt_context)
                        await self._send_email_to_recipient(
                            recipient_email=manager.email,
                            recipient_name=manager.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id,
                            attachments=attachments
                        )
                print(f"✅ Vehicle loaded emails sent to {len(managers)} Management users")

            # 2. Send to Customer
            if trip.customer.user and trip.customer.user.email:
                customer_context = {
                    **base_context,
                    "name": trip.customer.customer_name,
                    "is_management": False,
                    "is_vendor": False,
                    "is_customer": True
                }
                html_body = self._render_template("vehicale-loaded.html", customer_context)
                await self._send_email_to_recipient(
                    recipient_email=trip.customer.user.email,
                    recipient_name=trip.customer.customer_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id,
                    attachments=attachments
                )
                print(f"✅ Vehicle loaded email sent to Customer: {trip.customer.user.email}")

            # 3. Send to Vendor
            vendor_email = None
            vendor_name = trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "Vendor"
            
            if trip.assigned_vendor and trip.assigned_vendor.vendor:
                if trip.assigned_vendor.vendor.contact_persons:
                    vendor_email = trip.assigned_vendor.vendor.contact_persons[0].email
                if not vendor_email and trip.assigned_vendor.vendor.user:
                    vendor_email = trip.assigned_vendor.vendor.user.email
            
            if vendor_email:
                vendor_context = {
                    **base_context,
                    "name": vendor_name,
                    "is_management": False,
                    "is_vendor": True,
                    "is_customer": False
                }
                html_body = self._render_template("vehicale-loaded.html", vendor_context)
                await self._send_email_to_recipient(
                    recipient_email=vendor_email,
                    recipient_name=vendor_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id,
                    attachments=attachments
                )
                print(f"✅ Vehicle loaded email sent to Vendor: {vendor_email}")

        except Exception as e:
            print(f"❌ Error sending vehicle loaded emails: {str(e)}")

    async def send_vendor_advance_payment_approved_email(self, trip_id: UUID, request: Request, ) -> None:
        """
        Send Payment Approved notification emails to accountent.
        
        Args:
            trip_id: UUID of the trip
            request: FastAPI Request object for user context
        """
        try:
            from models import Trip, User, Role
            from models.trip import TripAddress, AddressTypeEnum, TripVendor
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload, selectinload
            from services.helper import administrative_user_id
            from uuid import UUID
            
            # Fetch trip details for email template
            trip_stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            trip_result = await self.session.execute(trip_stmt)
            trip_details = trip_result.unique().scalars().first()
            
            if trip_details and trip_details.assigned_vendor:
                # Format addresses for template
                loading_addresses = [
                    addr for addr in trip_details.addresses 
                    if addr.address_type == AddressTypeEnum.LOADING
                ]
                unloading_addresses = [
                    addr for addr in trip_details.addresses 
                    if addr.address_type == AddressTypeEnum.UNLOADING
                ]
                        
                def format_address(addr) -> str:
                    parts = []
                    if addr.location:
                        parts.append(addr.location)
                    if addr.city:
                        parts.append(addr.city.name)
                    if addr.district:
                        parts.append(addr.district.name)
                    if addr.state:
                        parts.append(addr.state.name)
                    if addr.country:
                        parts.append(addr.country.name)
                    if addr.pincode:
                        parts.append(f"PIN: {addr.pincode}")
                    return ", ".join(parts)
                
                loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
                unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
                        
                # Prepare template context
                email_context = {
                    "name": "{{name}}",  # Will be replaced per recipient
                    "trip_code": trip_details.trip_code,
                    "trip_rate": str(trip_details.trip_rate or 0),
                    "loading_unloading_charges": str(trip_details.loading_unloading_charges or 0),
                    "loading_date": trip_details.trip_date.strftime("%d-%m-%Y") if trip_details.trip_date else "N/A",
                    "vehicle_type": trip_details.vehicle_type.name if trip_details.vehicle_type else "N/A",
                    "capacity": trip_details.capacity or "N/A",
                    "types_of_good": trip_details.goods_name or "N/A",
                    "instructions_details": trip_details.instructions or "No special instructions",
                    "loading_details": loading_address_str or "N/A",
                    "unloading_details": unloading_address_str or "N/A",
                    "vendor_name": trip_details.assigned_vendor.vendor.vendor_name,
                    "vendor_branch_name": trip_details.branch.name if trip_details.branch else "N/A",
                    "vendor_trip_rate": str(trip_details.assigned_vendor.trip_rate or 0),
                    "vendor_other_charges": str((trip_details.assigned_vendor.other_charges or 0) + (trip_details.assigned_vendor.other_unloading_charges or 0)),
                    "vendor_advance": str(trip_details.assigned_vendor.advance or 0),
                    "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip_details.id}",
                }
                
                email_service = EmailNotificationService(self.session)
                subject = f"Complete Payment - {trip_details.trip_code}"
                
                # 1. Send to Management
                accountant_ids = await administrative_user_id(self.session, "accountant")
                if accountant_ids:
                    accountant_uuids = [UUID(id_str) for id_str in accountant_ids]
                    stmt_mgmt = select(User).filter(User.id.in_(accountant_uuids))
                    result_mgmt = await self.session.execute(stmt_mgmt)
                    accountants = result_mgmt.unique().scalars().all()
                

                for accountant in accountants:
                    if accountant.email:
                        # Update name for this recipient
                        email_context["name"] = accountant.name
                        html_body = email_service._render_template("vendor-advance-payment-approved.html", email_context)
                                
                        await email_service._send_email_to_recipient(
                            recipient_email=accountant.email,
                            recipient_name=accountant.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=user.id
                        )
                        print(f"✅ Payment completion email sent to accountant: {accountant.email}")
                    else:
                        print(f"⚠️ Accountant {accountant.name} has no email address")
                else:
                    print("⚠️ No accountants found for email notification")
                    
        except Exception as email_error:
            print(f"❌ Failed to send payment completion email to accountants: {str(email_error)}")

    async def send_vendor_advance_payment_approved_email(
        self,
        trip_id: UUID,
        request: Request,
    ) -> None:
        """
        Send vendor advance/balance payment approval emails to accountants.
        """
        try:
            from models import Trip, User
            from models.trip import TripAddress, AddressTypeEnum, TripVendor
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload, selectinload
            from services.helper import administrative_user_id
            from uuid import UUID
            
            # Fetch trip details for email template
            trip_stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            trip_result = await self.session.execute(trip_stmt)
            trip_details = trip_result.unique().scalars().first()
            
            if not trip_details or not trip_details.assigned_vendor:
                print(f"❌ Trip {trip_id} not found or has no assigned vendor for accountant email")
                return
            
            # Format addresses for template
            loading_addresses = [
                addr for addr in trip_details.addresses 
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip_details.addresses 
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]
                    
            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)
            
            loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
            unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])
                    
            # Base template context (per-recipient `name` will be added later)
            base_context = {
                "trip_code": trip_details.trip_code,
                "trip_rate": str(trip_details.trip_rate or 0),
                "loading_unloading_charges": str(trip_details.loading_unloading_charges or 0),
                "loading_date": trip_details.trip_date.strftime("%d-%m-%Y") if trip_details.trip_date else "N/A",
                "vehicle_type": trip_details.vehicle_type.name if trip_details.vehicle_type else "N/A",
                "capacity": trip_details.capacity or "N/A",
                "types_of_good": trip_details.goods_name or "N/A",
                "instructions_details": trip_details.instructions or "No special instructions",
                "loading_details": loading_address_str or "N/A",
                "unloading_details": unloading_address_str or "N/A",
                "vendor_name": trip_details.assigned_vendor.vendor.vendor_name,
                "vendor_branch_name": trip_details.branch.name if trip_details.branch else "N/A",
                "vendor_trip_rate": str(trip_details.assigned_vendor.trip_rate or 0),
                "vendor_other_charges": str(
                    (trip_details.assigned_vendor.other_charges or 0)
                    + (trip_details.assigned_vendor.other_unloading_charges or 0)
                ),
                "vendor_advance": str(trip_details.assigned_vendor.advance or 0),
                "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip_details.id}",
            }
            
            subject = f"Complete Payment - {trip_details.trip_code}"
            
            # Get accountant users
            accountant_ids = await administrative_user_id(self.session, "accountant")
            if not accountant_ids:
                print("⚠️ No accountants found for email notification")
                return
            
            accountant_uuids = [UUID(id_str) for id_str in accountant_ids]
            stmt_mgmt = select(User).filter(User.id.in_(accountant_uuids))
            result_mgmt = await self.session.execute(stmt_mgmt)
            accountants = result_mgmt.unique().scalars().all()
            
            for accountant in accountants:
                if not accountant.email:
                    print(f"⚠️ Accountant {accountant.name} has no email address")
                    continue
                
                context = {
                    **base_context,
                    "name": accountant.name,
                }
                html_body = self._render_template("vendor-advance-payment-approved.html", context)
                        
                await self._send_email_to_recipient(
                    recipient_email=accountant.email,
                    recipient_name=accountant.name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id,
                )
                print(f"✅ Payment completion email sent to accountant: {accountant.email}")
                    
        except Exception as email_error:
            print(f"❌ Failed to send payment completion email to accountants: {str(email_error)}")

        
    async def send_vendor_advance_payment_completed_email(
        self,
        trip_id: UUID,
        request: Request,
    ) -> None:
        """
        Send vendor advance payment completed emails to Vendor, Management and Supervisors.
        """
        try:
            from models import Trip, User
            from models.trip import TripAddress, AddressTypeEnum, TripVendor
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload, selectinload
            from services.helper import administrative_user_id, get_supervisors_in_branch
            from uuid import UUID

            # Fetch trip details for email template
            trip_stmt = (
                select(Trip)
                .options(
                    joinedload(Trip.customer),
                    joinedload(Trip.vehicle_type),
                    joinedload(Trip.branch),
                    joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor),
                    selectinload(Trip.addresses).joinedload(TripAddress.country),
                    selectinload(Trip.addresses).joinedload(TripAddress.state),
                    selectinload(Trip.addresses).joinedload(TripAddress.district),
                    selectinload(Trip.addresses).joinedload(TripAddress.city),
                )
                .filter(Trip.id == trip_id)
            )
            trip_result = await self.session.execute(trip_stmt)
            trip = trip_result.unique().scalars().first()

            if not trip or not trip.assigned_vendor:
                print(f"❌ Trip {trip_id} not found or has no assigned vendor for advance payment completed email")
                return

            # Format addresses
            loading_addresses = [
                addr for addr in trip.addresses
                if addr.address_type == AddressTypeEnum.LOADING
            ]
            unloading_addresses = [
                addr for addr in trip.addresses
                if addr.address_type == AddressTypeEnum.UNLOADING
            ]

            def format_address(addr) -> str:
                parts = []
                if addr.location:
                    parts.append(addr.location)
                if addr.city:
                    parts.append(addr.city.name)
                if addr.district:
                    parts.append(addr.district.name)
                if addr.state:
                    parts.append(addr.state.name)
                if addr.country:
                    parts.append(addr.country.name)
                if addr.pincode:
                    parts.append(f"PIN: {addr.pincode}")
                return ", ".join(parts)

            loading_address_str = "; ".join([format_address(a) for a in loading_addresses])
            unloading_address_str = "; ".join([format_address(a) for a in unloading_addresses])

            # Base template context (per-recipient `name` will be added later)
            base_context = {
                "trip_code": trip.trip_code,
                "trip_rate": str(trip.trip_rate or 0),
                "loading_unloading_charges": str(trip.loading_unloading_charges or 0),
                "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                "capacity": trip.capacity or "N/A",
                "types_of_good": trip.goods_name or "N/A",
                "instructions_details": trip.instructions or "No special instructions",
                "loading_details": loading_address_str or "N/A",
                "unloading_details": unloading_address_str or "N/A",
                "vendor_name": trip.assigned_vendor.vendor.vendor_name,
                "vendor_branch_name": trip.branch.name if trip.branch else "N/A",
                "vendor_trip_rate": str(trip.assigned_vendor.trip_rate or 0),
                "vendor_other_charges": str(
                    (trip.assigned_vendor.other_charges or 0)
                    + (trip.assigned_vendor.other_unloading_charges or 0)
                ),
                "vendor_advance": str(trip.assigned_vendor.advance or 0),
                "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip.id}",
            }

            subject = f"Advance Payment Completed - {trip.trip_code}"

            # 1. Send to Vendor
            vendor_email = None
            vendor_name = trip.assigned_vendor.vendor.vendor_name

            if trip.assigned_vendor.vendor.contact_persons:
                vendor_email = trip.assigned_vendor.vendor.contact_persons[0].email
            if not vendor_email and trip.assigned_vendor.vendor.user:
                vendor_email = trip.assigned_vendor.vendor.user.email

            if vendor_email:
                vendor_context = {
                    **base_context,
                    "name": vendor_name,
                    "role": "Vendor",
                }
                html_body = self._render_template(
                    "vendor-advance-payment-completed.html",
                    vendor_context,
                )
                await self._send_email_to_recipient(
                    recipient_email=vendor_email,
                    recipient_name=vendor_name,
                    subject=subject,
                    html_body=html_body,
                    created_by_id=request.state.user.id,
                )
                print(f"✅ Advance payment completed email sent to Vendor: {vendor_email}")
            else:
                print(f"⚠️ No email found for Vendor {vendor_name}")

            # 2. Send to Management
            management_ids = await administrative_user_id(self.session, "management")
            if management_ids:
                management_uuids = [UUID(id_str) for id_str in management_ids]
                stmt_mgmt = select(User).filter(User.id.in_(management_uuids))
                result_mgmt = await self.session.execute(stmt_mgmt)
                managers = result_mgmt.unique().scalars().all()

                for manager in managers:
                    if not manager.email:
                        print(f"⚠️ Management user {manager.name} has no email address")
                        continue

                    mgmt_context = {
                        **base_context,
                        "name": manager.name,
                        "role": "Management",
                    }
                    html_body = self._render_template(
                        "vendor-advance-payment-completed.html",
                        mgmt_context,
                    )
                    await self._send_email_to_recipient(
                        recipient_email=manager.email,
                        recipient_name=manager.name,
                        subject=subject,
                        html_body=html_body,
                        created_by_id=request.state.user.id,
                    )
                print(f"✅ Advance payment completed emails sent to {len(managers)} Management users")
            else:
                print("⚠️ No management users found for advance payment completed email")

            # 3. Send to Supervisors
            supervisor_ids = await get_supervisors_in_branch(self.session, trip.branch_id)
            if supervisor_ids:
                supervisor_uuids = [UUID(id_str) for id_str in supervisor_ids]
                stmt_supervisors = (
                    select(User)
                    .filter(User.id.in_(supervisor_uuids))
                )
                result_supervisors = await self.session.execute(stmt_supervisors)
                supervisors = result_supervisors.unique().scalars().all()

                for supervisor in supervisors:
                    if not supervisor.email:
                        print(f"⚠️ Supervisor {supervisor.name} has no email address")
                        continue

                    supervisor_context = {
                        **base_context,
                        "name": supervisor.name,
                        "role": "Supervisor",
                    }
                    html_body = self._render_template(
                        "vendor-advance-payment-completed.html",
                        supervisor_context,
                    )
                    await self._send_email_to_recipient(
                        recipient_email=supervisor.email,
                        recipient_name=supervisor.name,
                        subject=subject,
                        html_body=html_body,
                        created_by_id=request.state.user.id,
                    )
                print(f"✅ Advance payment completed emails sent to {len(supervisors)} supervisors")
            else:
                print("⚠️ No supervisors found for advance payment completed email")

        except Exception as email_error:
            print(f"❌ Failed to send advance payment completed emails: {str(email_error)}")

    async def send_vehicle_unloaded_email(
            self,
            trip_id: UUID,
            request: Request
        ) -> None:
            """
            Send vehicle unloaded notification emails to Branch Managers (and Management) and
            attach POD document if it has been submitted.
            """
            from models import Trip, Customer, Vendor, Employee, User
            from models.trip import TripAddress, AddressTypeEnum, TripVendor, TripDocument
            from models.vendor import VendorContactPerson
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload, selectinload
            from services.helper import get_branch_manager_id, administrative_user_id
            from uuid import UUID
            import os

            try:
                # Fetch trip with all necessary relationships
                stmt = (
                    select(Trip)
                    .options(
                        joinedload(Trip.customer).joinedload(Customer.user),
                        joinedload(Trip.vehicle_type),
                        joinedload(Trip.branch),
                        joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).joinedload(Vendor.user),
                        joinedload(Trip.assigned_vendor).joinedload(TripVendor.vendor).selectinload(Vendor.contact_persons),
                        joinedload(Trip.assigned_vendor).selectinload(TripVendor.drivers),
                        selectinload(Trip.addresses).joinedload(TripAddress.country),
                        selectinload(Trip.addresses).joinedload(TripAddress.state),
                        selectinload(Trip.addresses).joinedload(TripAddress.district),
                        selectinload(Trip.addresses).joinedload(TripAddress.city),
                        joinedload(Trip.trip_documents),
                    )
                    .filter(Trip.id == trip_id)
                )
                result = await self.session.execute(stmt)
                trip = result.unique().scalars().first()

                if not trip:
                    print(f"❌ Trip {trip_id} not found for vehicle unloaded email")
                    return

                # Prepare POD attachment (if any)
                attachments: list[str] = []
                is_pod_attached = False
                if trip.trip_documents and trip.trip_documents.pod_submit:
                    pod_path = trip.trip_documents.pod_submit
                    if os.path.exists(pod_path):
                        attachments.append(pod_path)
                        is_pod_attached = True

                # Format addresses
                loading_addresses = [
                    addr for addr in trip.addresses
                    if addr.address_type == AddressTypeEnum.LOADING
                ]
                unloading_addresses = [
                    addr for addr in trip.addresses
                    if addr.address_type == AddressTypeEnum.UNLOADING
                ]

                def format_address(addr) -> str:
                    parts = []
                    if addr.location:
                        parts.append(addr.location)
                    if addr.city:
                        parts.append(addr.city.name)
                    if addr.district:
                        parts.append(addr.district.name)
                    if addr.state:
                        parts.append(addr.state.name)
                    if addr.country:
                        parts.append(addr.country.name)
                    if addr.pincode:
                        parts.append(f"PIN: {addr.pincode}")
                    return ", ".join(parts)

                loading_address_str = "; ".join([format_address(addr) for addr in loading_addresses])
                unloading_address_str = "; ".join([format_address(addr) for addr in unloading_addresses])

                # Prepare base template context
                base_context = {
                    "trip_code": trip.trip_code,
                    "trip_rate": trip.trip_rate,
                    "loading_unloading_charges": trip.loading_unloading_charges,
                    "loading_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                    "vehicle_type": trip.vehicle_type.name if trip.vehicle_type else "N/A",
                    "capacity": trip.capacity or "N/A",
                    "types_of_good": trip.goods_name,
                    "loading_details": loading_address_str or "N/A",
                    "unloading_details": unloading_address_str or "N/A",
                    "instructions_details": trip.instructions or "No special instructions",
                    "company_name": "Eisaku",
                    "current_year": datetime.now().year,
                    # Vehicle Details
                    "assigned_vehicle_type": trip.assigned_vendor.vehicle_type.name if trip.assigned_vendor and trip.assigned_vendor.vehicle_type else "N/A",
                    "assigned_vehicle_number": trip.assigned_vendor.vehicle_no if trip.assigned_vendor else "N/A",
                    "assigned_vehicle_capacity": trip.assigned_vendor.tons if trip.assigned_vendor else "N/A",
                    "assigned_vehicle_insurance_expiry": trip.assigned_vendor.insurance_expiry_date.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.insurance_expiry_date else "N/A",
                    # Driver Details
                    "driver_name": trip.assigned_vendor.drivers[0].driver_name if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                    "driver_mobile": trip.assigned_vendor.drivers[0].driver_mobile_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                    "driver_licence": trip.assigned_vendor.drivers[0].driver_licence_no if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                    "driver_license_expiry": trip.assigned_vendor.drivers[0].driver_licence_expiry.strftime("%d-%m-%Y") if trip.assigned_vendor and trip.assigned_vendor.drivers else "N/A",
                    # Vendor / Fleet
                    "vendor_name": trip.assigned_vendor.vendor.vendor_name if trip.assigned_vendor else "N/A",
                    "vendor_branch_name": trip.branch.name if trip.branch else "N/A",
                    "vendor_trip_rate": trip.assigned_vendor.trip_rate if trip.assigned_vendor else "N/A",
                    "vendor_other_charges": (trip.assigned_vendor.other_charges + trip.assigned_vendor.other_unloading_charges) if trip.assigned_vendor else "N/A",
                    "vendor_advance": trip.assigned_vendor.advance if trip.assigned_vendor else "N/A",
                    "start_date": trip.trip_date.strftime("%d-%m-%Y") if trip.trip_date else "N/A",
                    "web_url": f"http://157.173.219.215:3000/market-trip/view/{trip.id}",
                    "trip_id": str(trip.id),
                    "is_pod_attached": is_pod_attached,
                }

                subject = f"Vehicle Unloaded - {trip.trip_code}"

                # 1. Send to Branch Managers
                manager_ids = await get_branch_manager_id(self.session, trip.branch_id)
                if manager_ids:
                    manager_uuids = [UUID(id_str) for id_str in manager_ids]
                    stmt_managers = (
                        select(User)
                        .join(Employee, Employee.user_id == User.id)
                        .filter(User.id.in_(manager_uuids))
                    )
                    result_managers = await self.session.execute(stmt_managers)
                    managers = result_managers.unique().scalars().all()

                    for manager in managers:
                        if not manager.email:
                            continue
                        context = {
                            **base_context,
                            "name": manager.name,
                            "is_branch_manager": True,
                            "is_management": False,
                            "is_customer": False,
                            "is_vendor": False,
                        }
                        html_body = self._render_template("vehicle-unloaded.html", context)
                        await self._send_email_to_recipient(
                            recipient_email=manager.email,
                            recipient_name=manager.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id,
                            attachments=attachments,
                        )
                    print(f"✅ Vehicle unloaded emails sent to {len(managers)} Branch Managers")

                # 2. Send to Management as well (optional, aligns with notifications)
                management_ids = await administrative_user_id(self.session, "management")
                if management_ids:
                    management_uuids = [UUID(id_str) for id_str in management_ids]
                    stmt_mgmt = select(User).filter(User.id.in_(management_uuids))
                    result_mgmt = await self.session.execute(stmt_mgmt)
                    management_users = result_mgmt.unique().scalars().all()

                    for m_user in management_users:
                        if not m_user.email:
                            continue
                        context = {
                            **base_context,
                            "name": m_user.name,
                            "is_branch_manager": False,
                            "is_management": True,
                            "is_customer": False,
                            "is_vendor": False,
                        }
                        html_body = self._render_template("vehicle-unloaded.html", context)
                        await self._send_email_to_recipient(
                            recipient_email=m_user.email,
                            recipient_name=m_user.name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id,
                            attachments=attachments,
                        )
                    print(f"✅ Vehicle unloaded emails sent to {len(management_users)} Management users")

                # 3. Send to Customer
                if trip.customer and trip.customer.user and trip.customer.user.email:
                    customer_context = {
                        **base_context,
                        "name": trip.customer.customer_name,
                        "is_branch_manager": False,
                        "is_management": False,
                        "is_customer": True,
                        "is_vendor": False,
                    }
                    html_body = self._render_template("vehicle-unloaded.html", customer_context)
                    await self._send_email_to_recipient(
                        recipient_email=trip.customer.user.email,
                        recipient_name=trip.customer.customer_name,
                        subject=subject,
                        html_body=html_body,
                        created_by_id=request.state.user.id,
                        attachments=attachments,
                    )
                    print(f"✅ Vehicle unloaded email sent to Customer: {trip.customer.customer_name}")
                else:
                    print(f"⚠️ No customer email found for trip {trip.trip_code}")

                # 4. Send to Vendor
                if trip.assigned_vendor and trip.assigned_vendor.vendor:
                    vendor_email = None
                    vendor_name = trip.assigned_vendor.vendor.vendor_name
                    
                    # Try contact persons first
                    if trip.assigned_vendor.vendor.contact_persons:
                        # Prefer primary contact or first one
                        vendor_email = trip.assigned_vendor.vendor.contact_persons[0].email
                    
                    # Fallback to user email
                    if not vendor_email and trip.assigned_vendor.vendor.user:
                        vendor_email = trip.assigned_vendor.vendor.user.email
                    
                    if vendor_email:
                        vendor_context = {
                            **base_context,
                            "name": vendor_name,
                            "is_branch_manager": False,
                            "is_management": False,
                            "is_customer": False,
                            "is_vendor": True,
                        }
                        html_body = self._render_template("vehicle-unloaded.html", vendor_context)
                        await self._send_email_to_recipient(
                            recipient_email=vendor_email,
                            recipient_name=vendor_name,
                            subject=subject,
                            html_body=html_body,
                            created_by_id=request.state.user.id,
                            attachments=attachments,
                        )
                        print(f"✅ Vehicle unloaded email sent to Vendor: {vendor_name}")
                    else:
                        print(f"⚠️ No email found for Vendor {vendor_name}")
                else:
                    print(f"⚠️ No assigned vendor found for trip {trip.trip_code}")

            except Exception as e:
                print(f"❌ Error sending vehicle unloaded emails: {str(e)}")