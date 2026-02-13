from core.websocket_manager import manager
from services.mail import send_email
from utils.email_helper import get_trip_email_content
from datetime import datetime
from sqlmodel import Session
from fastapi import Request
from models import User, Customer, Employee
from models.role import Role

async def send_trip_notification_and_email(
    session: Session,
    request: Request,
    trip,
    status: str,
    recipients: list[str],
):
    """
    Send WebSocket notifications and emails for trip status changes.
    
    Args:
        session: Database session
        request: FastAPI request
        trip: Trip object
        status: Status key from email.json (e.g., 'pending', 'approved', etc.)
        recipients: List of recipient types to notify
    """
    
    # Map status to notification types
    notification_type_map = {
        'pending': 'trip_pending',
        'approved': 'trip_approved',
        'rejected': 'trip_rejected',
        'vendor_assigned': 'trip_vendor_assigned',
        'driver_assigned': 'trip_driver_assigned',
        'fleet_rate_approve': 'trip_rate_approved',
        'flit_rate_reject': 'trip_rate_rejected',
        'vehicle_loaded': 'trip_vehicle_loaded',
        'vehicle_unloaded': 'trip_vehicle_unloaded',
        'advance_payment': 'trip_advance_payment',
        'pod_submitted': 'trip_pod_submitted',
        'in_transit': 'trip_in_transit',
        'completed': 'trip_completed',
    }
    
    notification_type = notification_type_map.get(status.lower(), 'trip_updated')
    
    # Get email content
    email_context = {
        'trip_code': trip.trip_code,
        'trip_date': str(trip.trip_date),
        'trip_status': trip.status.value,
    }
    
    # ✅ Notify Creator
    if 'creator' in recipients and trip.created_by:
        creator = session.get(User, trip.created_by)
        if creator:
            # WebSocket notification
            notification = {
                "type": notification_type,
                "message": f"Trip {trip.trip_code} status updated to {trip.status.value}",
                "trip_id": str(trip.id),
                "trip_code": trip.trip_code,
                "status": trip.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"📨 Sending notification to creator: {creator.id}")
            await manager.send_personal_notification(
                str(creator.id),
                notification,
                db_session=session
            )
            
            # Email
            email_context['username'] = creator.name
            header, body = get_trip_email_content(status, email_context)
            
            try:
                await send_email(
                    session=session,
                    request=request,
                    recipient_email=creator.email,
                    recipient_name=creator.name,
                    header_msg=header,
                    body_msg=body
                )
                print(f"✉️ Email sent to creator: {creator.email}")
            except Exception as e:
                print(f"❌ Failed to send email to creator: {str(e)}")
    
    # ✅ Notify Customer
    if 'customer' in recipients and trip.customer_id:
        customer = session.get(Customer, trip.customer_id)
        if customer and customer.user_id:
            customer_user = session.get(User, customer.user_id)
            if customer_user:
                # WebSocket notification
                notification = {
                    "type": notification_type,
                    "message": f"Trip {trip.trip_code} status updated to {trip.status.value}",
                    "trip_id": str(trip.id),
                    "trip_code": trip.trip_code,
                    "status": trip.status.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                print(f"📨 Sending notification to customer: {customer.user_id}")
                await manager.send_personal_notification(
                    str(customer.user_id),
                    notification,
                    db_session=session
                )
                
                # Email
                email_context['username'] = customer_user.name
                email_context['customer_code'] = customer.customer_code
                header, body = get_trip_email_content(status, email_context)
                
                try:
                    await send_email(
                        session=session,
                        request=request,
                        recipient_email=customer_user.email,
                        recipient_name=customer_user.name,
                        header_msg=header,
                        body_msg=body
                    )
                    print(f"✉️ Email sent to customer: {customer_user.email}")
                except Exception as e:
                    print(f"❌ Failed to send email to customer: {str(e)}")
    
    # ✅ Notify Branch Manager
    if 'branch_manager' in recipients and trip.branch_id:
        branch_manager = (
            session.query(Employee)
            .join(User, Employee.user_id == User.id)
            .join(Role, User.role_id == Role.id)
            .filter(
                Employee.branch_id == trip.branch_id,
                Role.name == "branch manager",
                Employee.is_active == True,
                User.is_active == True
            )
            .first()
        )
        
        if branch_manager and branch_manager.user_id:
            branch_manager_user = branch_manager.user
            
            # WebSocket notification
            notification = {
                "type": notification_type,
                "message": f"Trip {trip.trip_code} status updated to {trip.status.value}",
                "trip_id": str(trip.id),
                "trip_code": trip.trip_code,
                "status": trip.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"📨 Sending notification to branch manager: {branch_manager.user_id}")
            await manager.send_personal_notification(
                str(branch_manager.user_id),
                notification,
                db_session=session
            )
            
            # Email
            email_context['username'] = branch_manager_user.name
            header, body = get_trip_email_content(status, email_context)
            
            try:
                await send_email(
                    session=session,
                    request=request,
                    recipient_email=branch_manager_user.email,
                    recipient_name=branch_manager_user.name,
                    header_msg=header,
                    body_msg=body
                )
                print(f"✉️ Email sent to branch manager: {branch_manager_user.email}")
            except Exception as e:
                print(f"❌ Failed to send email to branch manager: {str(e)}")
