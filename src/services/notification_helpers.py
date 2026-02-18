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
TRIP_APPROVED = "trip_approved"
VENDOR_ASSIGNED = "vendor_assigned"
VEHICAL_LOADING_PENDING = "vehical_loading_pending"
VEHICAL_LOADING_APPROVED = "vehical_loading_approved"
ADVANCE_PAYMENT_REJECTED = "advance_payment_rejected"
ADVANCE_PAYMENT_VENDOR_PENDING = "advance_payment_vendor_pending"
ADVANCE_PAYMENT_VENDOR_APPROVED = "advance_payment_vendor_approved"
TRIP_APPROVAL = "trip_approval"

TRIP_CREATED = "trip_created"
TRIP_STATUS_CHANGE = "trip_status_change"
VENDOR_ASSIGNMENT = "vendor_assignment"
FLIT_RATE_APPROVAL = "flit_rate_approval"
FLIT_RATE_APPROVED = "flit_rate_approved"
VENDOR_ADVANCE_PAYMENT_APPROVAL = "vendor_advance_payment_approval"
VENDOR_ADVANCE_PAYMENT_APPROVED = "vendor_advance_payment_approved"
VENDOR_ADVANCE_PAYMENT_COMPLETED = "vendor_advance_payment_completed"
VEHICAL_UNLOADED = "vehical_unloaded"
POD_SUBMITED = "pod_submited"
BALANCE_PAYMENT_REQUIRED = "balance_payment_required"
BALANCE_PAYMENT_APPROVED = "balance_payment_approved"
TRIP_COMPLETED = "trip_completed"


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
            notification_type=TRIP_CREATED,
            user_ids=user_ids,
            message=f"Trip {trip_code} Created!",
            action_required=True,
            action_data={
                "buttons": [
                    {"name": "approve", "url": f"{base_url}/api/v1/trips/{trip_id}/status/"},
                    {"name": "reject", "url": f"{base_url}/api/v1/trips/{trip_id}/status/"}
                ],
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
            action_deadline=action_deadline,
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Handle datetime serialization for JSON
        if 'action_deadline' in notification_dict and notification_dict['action_deadline']:
            notification_dict['action_deadline'] = notification_dict['action_deadline'].isoformat()
        
        # Send to users via socket_manager
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )
    
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
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
            action_deadline=None,
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        # Send to supervisors in the branch
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
            )
    
    async def assign_vendor_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification for supervisors to assign vendor after trip approval"""

        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"

        notification_data = NotificationCreate(
            notification_type=VENDOR_ASSIGNMENT,
            user_ids=user_ids,
            role="supervisor",
            message=f"Trip {trip_code} has been approved - please assign a vendor",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
            notification_type=VENDOR_ADVANCE_PAYMENT_APPROVAL,
            user_ids=user_ids,
            role=None,
            message=f"Approve Advance Payment for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-advance-payment/view",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
            notification_type=VENDOR_ADVANCE_PAYMENT_APPROVED,
            user_ids=user_ids,
            role=None,
            message=f"Advance Payment Approved, Release Payment for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
 
    async def advance_payment_completed_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:  
        """Create notification for management to approve advance payment when vehicle is loaded"""
        
        notification_data = NotificationCreate(
            notification_type=VENDOR_ADVANCE_PAYMENT_COMPLETED,
            user_ids=user_ids,
            role=None,
            message=f"Advance Payment Completed for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
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
    
    
    async def vehicle_unloaded_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification when vehicle is unloaded"""
        
        notification_data = NotificationCreate(
            notification_type=VEHICAL_UNLOADED,
            user_ids=user_ids,
            message=f"Vehicle unloaded for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )
    
    async def pod_submitted_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification when POD is submitted"""
        
        notification_data = NotificationCreate(
            notification_type=POD_SUBMITED,
            user_ids=user_ids,
            message=f"POD submitted for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
        )
        
        # Convert to dictionary for socket_manager
        notification_dict = notification_data.model_dump()
        
        await socket_manager.send_to_users(
            user_ids=user_ids, 
            notification=notification_dict,
            db_session=None  # Notification service handles DB save
        )


    async def pending_balance_payment_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification when balance payment is pending"""
        
        notification_data = NotificationCreate(
            notification_type=BALANCE_PAYMENT_REQUIRED,
            user_ids=user_ids,
            message=f"Balance payment required for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
        )
        
        await self.notification_service.create_notification(notification_data, request)

    async def balance_payment_approved_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification when balance payment is approved"""
        
        notification_data = NotificationCreate(
            notification_type=BALANCE_PAYMENT_APPROVED,
            user_ids=user_ids,
            message=f"Balance payment approved for Trip {trip_code}",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
        )
        
        await self.notification_service.create_notification(notification_data, request)

    async def trip_completed_notification(self, user_ids: List[str], trip_id: UUID, trip_code: str, request: Request) -> None:
        """Create notification when trip is completed"""
        
        notification_data = NotificationCreate(
            notification_type=TRIP_COMPLETED,
            user_ids=user_ids,
            message=f"Trip {trip_code} has been completed",
            action_required=True,
            action_data={
                "redirect_url": f"market-trip/view/{trip_id}",
                "redirect_screen": "ViewMarketTrip",
                "redirect_id": str(trip_id)
            },
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
