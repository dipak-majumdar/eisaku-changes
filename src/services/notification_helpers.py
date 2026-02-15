from uuid import UUID
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from core.websocket_manager import socket_manager

from schemas.notifications import NotificationCreate
from services.notifications import NotificationService

USER_CREATED = "user_created"
VENDOR_CREATED = "vendor_created"
TRIP_APPROVAL = "trip_approval"
TRIP_APPROVED = "trip_approved"
TRIP_STATUS_CHANGE = "trip_status_change"
VENDOR_ASSIGNMENT = "vendor_assignment"
VENDOR_ASSIGNED = "vendor_assigned"
FLIT_RATE_APPROVAL = "flit_rate_approval"
FLIT_RATE_APPROVED = "flit_rate_approved"
VEHICAL_LOADING_PENDING = "vehical_loading_pending"
VEHICAL_LOADING_APPROVED = "vehical_loading_approved"
ADVANCE_PAYMENT_APPROVAL = "advance_payment_approval"
ADVANCE_PAYMENT_APPROVED = "advance_payment_approved"
ADVANCE_PAYMENT_REJECTED = "advance_payment_rejected"
ADVANCE_PAYMENT_VENDOR_PENDING = "advance_payment_vendor_pending"
ADVANCE_PAYMENT_VENDOR_APPROVED = "advance_payment_vendor_approved"
VEHICAL_UNLOADED = "vehical_unloaded"
POD_SUBMITED = "pod_submited"

BASE_URL  = f"{request.url.scheme}://{request.url.netloc}"


class NotificationHelper:
    """Helper class for creating different types of notifications"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.notification_service = NotificationService(session)
    
    async def new_trip_created(
        self,
        user_ids: List[str],
        trip_id: UUID,
        trip_code: str,
        request: Request,
        deadline_hours: int = 0.17  # 10 minutes (10/60 = 0.17 hours)
    ) -> None:
        """Create notification for trip approval request"""
        action_deadline = datetime.utcnow() + timedelta(hours=deadline_hours)
        
        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        notification_data = NotificationCreate(
            notification_type=TRIP_APPROVAL,
            user_ids=user_ids,
            message=f"Trip {trip_code} Created!",
            action_required=True,
            action_data={
                "buttons": [
                    {"name": "approve", "url": f"{base_url}/api/v1/trips/{trip_id}/status/"},
                    {"name": "reject", "url": f"{base_url}/api/v1/trips/{trip_id}/status/"}
                ],
                "redirect_url": f"{base_url}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
            action_deadline=action_deadline,
            is_read=False
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    async def trip_status_changed(
        self,
        user_ids: List[str],
        trip_id: UUID,
        trip_code: str,
        previous_status: str,
        new_status: str,
        request: Request,
        remarks: Optional[str] = None
    ) -> None:
        """Create notification for trip status change"""
        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"

        notification_data = NotificationCreate(
            notification_type=TRIP_STATUS_CHANGE,
            user_ids=user_ids,
            message=f"Trip {trip_code} status changed from {previous_status} to {new_status}",
            action_required=True,
            action_data={
                "redirect_url": f"{base_url}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
            action_deadline=None,
            is_read=False
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    
    async def assign_vendor_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification for supervisors to assign vendor after trip approval"""

        notification_data = NotificationCreate(
            notification_type=VENDOR_ASSIGNMENT,
            user_ids=user_ids,
            role="supervisor",
            message=f"Trip {trip_code} has been approved - please assign a vendor",
            action_required=True,
            action_data={
                "redirect_url": f"{BASE_URL}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to supervisors in the branch
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )

    async def approve_flit_rate_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification for vendors to assign vendor after trip approval"""
        
        notification_data = NotificationCreate(
            notification_type=FLIT_RATE_APPROVAL,
            user_ids=user_ids,
            role=None,
            message=f"Approve Flip Rate for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"{BASE_URL}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to branch manager/management
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )

    async def flit_rate_approved_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification for vendors to assign vendor after trip approval"""
        
        notification_data = NotificationCreate(
            notification_type=FLIT_RATE_APPROVED,
            user_ids=user_ids,
            role=None,
            message=f"Flit Rate Approved, Start Loading Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"{BASE_URL}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to branch manager/management
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )

    async def vehicle_loaded_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification for management to approve advance payment when vehicle is loaded"""
        
        notification_data = NotificationCreate(
            notification_type=ADVANCE_PAYMENT_APPROVAL,
            user_ids=user_ids,
            role=None,
            message=f"Approve Advance Payment for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"{BASE_URL}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to management
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )
    
    async def advance_payment_approved_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:  
        """Create notification for management to approve advance payment when vehicle is loaded"""
        
        notification_data = NotificationCreate(
            notification_type=ADVANCE_PAYMENT_APPROVED,
            user_ids=user_ids,
            role=None,
            message=f"Approve Advance Payment for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"{BASE_URL}/trips/{trip_id}",
                "redirect_screen": "ViewMarketTrip"
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to management
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )
    
    async def create_vendor_registration_notification(
        self,
        user_ids: List[str],
        vendor_id: UUID,
        vendor_name: str,
        request: Request,
        deadline_hours: int = 48
    ) -> None:
        """Create notification for new vendor registration approval"""
        action_deadline = datetime.utcnow() + timedelta(hours=deadline_hours)
        
        notification_data = NotificationCreate(
            user_ids=user_ids,
            notification_type="vendor_approval",
            message=f"New vendor '{vendor_name}' registration requires approval",
            action_required=True,
            action_data={
                "vendor_id": str(vendor_id),
                "vendor_name": vendor_name,
                "action_url": f"/vendors/{vendor_id}/approve"
            },
            action_deadline=action_deadline,
            is_read=False
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    async def create_payment_notification(
        self,
        user_ids: List[str],
        payment_id: str,
        amount: float,
        payment_type: str,
        request: Request
    ) -> None:
        """Create notification for payment received/pending"""
        notification_data = NotificationCreate(
            user_ids=user_ids,
            notification_type="payment",
            message=f"Payment {payment_type}: ${amount:.2f} {'received' if payment_type == 'received' else 'pending'}",
            action_required=payment_type == "pending",
            action_data={
                "payment_id": payment_id,
                "amount": amount,
                "payment_type": payment_type,
                "action_url": f"/payments/{payment_id}" if payment_type == "pending" else None
            }
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    async def create_complaint_notification(
        self,
        user_ids: UUID,
        complaint_id: str,
        complaint_type: str,
        priority: str,
        request: Request,
        deadline_hours: int = 72
    ) -> None:
        """Create notification for new complaint"""
        action_deadline = datetime.utcnow() + timedelta(hours=deadline_hours)
        
        notification_data = NotificationCreate(
            user_id=user_id,
            notification_type="complaint",
            message=f"New {priority} priority {complaint_type} complaint registered",
            action_required=True,
            action_data={
                "complaint_id": complaint_id,
                "complaint_type": complaint_type,
                "priority": priority,
                "action_url": f"/complaints/{complaint_id}"
            },
            action_deadline=action_deadline
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    async def create_system_notification(
        self,
        user_ids: List[UUID],
        message: str,
        request: Request,
        notification_type: str = "system",
        action_required: bool = False,
        action_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create system notification for multiple users"""
        for user_id in user_ids:
            notification_data = NotificationCreate(
                user_id=user_id,
                notification_type=notification_type,
                message=message,
                action_required=action_required,
                action_data=action_data
            )
            
            await self.notification_service.create_notification(notification_data, request)
    
    async def create_deadline_reminder(
        self,
        user_id: UUID,
        task_type: str,
        task_id: str,
        deadline: datetime,
        request: Request
    ) -> None:
        """Create deadline reminder notification"""
        hours_until_deadline = (deadline - datetime.utcnow()).total_seconds() / 3600
        
        if hours_until_deadline <= 0:
            urgency = "OVERDUE"
        elif hours_until_deadline <= 24:
            urgency = "URGENT"
        elif hours_until_deadline <= 72:
            urgency = "SOON"
        else:
            urgency = "REMINDER"
        
        notification_data = NotificationCreate(
            user_id=user_id,
            notification_type="deadline_reminder",
            message=f"{urgency}: {task_type} {task_id} deadline approaching",
            action_required=True,
            action_data={
                "task_type": task_type,
                "task_id": task_id,
                "deadline": deadline.isoformat(),
                "urgency": urgency,
                "action_url": f"/{task_type}s/{task_id}"
            },
            action_deadline=deadline,
            is_read=False
        )
        
        await self.notification_service.create_notification(notification_data, request)
    
    async def create_welcome_notification(
        self,
        user_id: UUID,
        user_name: str,
        request: Request
    ) -> None:
        """Create welcome notification for new users"""
        notification_data = NotificationCreate(
            user_id=user_id,
            notification_type="welcome",
            message=f"Welcome to TMS, {user_name}! Your account has been created successfully.",
            action_required=False,
            action_data={
                "user_name": user_name,
                "action_url": "/dashboard"
            }
        )
        
        await self.notification_service.create_notification(notification_data, request)


# Convenience functions for common notification types
async def notify_trip_approval(
    session: AsyncSession,
    user_id: UUID,
    trip_id: str,
    trip_details: Dict[str, Any],
    request: Request,
    deadline_hours: int = 24
) -> None:
    """Convenience function for trip approval notifications"""
    helper = NotificationHelper(session)
    await helper.create_trip_approval_notification(
        user_id, trip_id, trip_details, request, deadline_hours
    )



async def notify_vendor_registration(
    session: AsyncSession,
    user_id: UUID,
    vendor_id: UUID,
    vendor_name: str,
    request: Request,
    deadline_hours: int = 48
) -> None:
    """Convenience function for vendor registration notifications"""
    helper = NotificationHelper(session)
    await helper.create_vendor_registration_notification(
        user_id, vendor_id, vendor_name, request, deadline_hours
    )


async def notify_payment(
    session: AsyncSession,
    user_id: UUID,
    payment_id: str,
    amount: float,
    payment_type: str,
    request: Request
) -> None:
    """Convenience function for payment notifications"""
    helper = NotificationHelper(session)
    await helper.create_payment_notification(
        user_id, payment_id, amount, payment_type, request
    )


async def notify_complaint(
    session: AsyncSession,
    user_id: UUID,
    complaint_id: str,
    complaint_type: str,
    priority: str,
    request: Request,
    deadline_hours: int = 72
) -> None:
    """Convenience function for complaint notifications"""
    helper = NotificationHelper(session)
    await helper.create_complaint_notification(
        user_id, complaint_id, complaint_type, priority, request, deadline_hours
    )


async def notify_system(
    session: AsyncSession,
    user_ids: List[UUID],
    message: str,
    request: Request,
    notification_type: str = "system",
    action_required: bool = False,
    action_data: Optional[Dict[str, Any]] = None
) -> None:
    """Convenience function for system notifications"""
    helper = NotificationHelper(session)
    await helper.create_system_notification(
        user_ids, message, notification_type, action_required, action_data, request
    )
