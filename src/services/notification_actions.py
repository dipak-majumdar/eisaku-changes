from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import json
import logging

logger = logging.getLogger(__name__)


class NotificationActionHandler(ABC):
    """Abstract base class for notification action handlers"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @abstractmethod
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle the notification action"""
        pass
    
    @abstractmethod
    def get_supported_actions(self) -> list[str]:
        """Return list of supported actions"""
        pass


class TripApprovalHandler(NotificationActionHandler):
    """Handler for trip approval notifications"""
    
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle trip approval/rejection actions"""
        trip_id = action_data.get("trip_id")
        
        if not trip_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trip ID is required"
            )
        
        if action == "accept":
            # Here you would typically:
            # 1. Update trip status to approved
            # 2. Send notifications to relevant parties
            # 3. Log the approval
            result = {
                "success": True,
                "message": f"Trip {trip_id} approved successfully",
                "trip_id": trip_id,
                "status": "approved",
                "approved_by": str(user_id)
            }
            
        elif action == "reject":
            rejection_reason = action_data.get("rejection_reason", "No reason provided")
            
            # Here you would typically:
            # 1. Update trip status to rejected
            # 2. Send notifications to relevant parties
            # 3. Log the rejection
            result = {
                "success": True,
                "message": f"Trip {trip_id} rejected",
                "trip_id": trip_id,
                "status": "rejected",
                "rejected_by": str(user_id),
                "rejection_reason": rejection_reason
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {action}"
            )
        
        logger.info(f"Trip {trip_id} {action} by user {user_id}")
        return result
    
    def get_supported_actions(self) -> list[str]:
        return ["accept", "reject"]


class VendorApprovalHandler(NotificationActionHandler):
    """Handler for vendor registration approval notifications"""
    
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle vendor approval/rejection actions"""
        vendor_id = action_data.get("vendor_id")
        
        if not vendor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vendor ID is required"
            )
        
        if action == "approve":
            # Here you would typically:
            # 1. Update vendor status to approved
            # 2. Send welcome notification to vendor
            # 3. Set up vendor account access
            result = {
                "success": True,
                "message": f"Vendor {vendor_id} approved successfully",
                "vendor_id": vendor_id,
                "status": "approved",
                "approved_by": str(user_id)
            }
            
        elif action == "reject":
            rejection_reason = action_data.get("rejection_reason", "Requirements not met")
            
            # Here you would typically:
            # 1. Update vendor status to rejected
            # 2. Send rejection notification to vendor
            result = {
                "success": True,
                "message": f"Vendor {vendor_id} rejected",
                "vendor_id": vendor_id,
                "status": "rejected",
                "rejected_by": str(user_id),
                "rejection_reason": rejection_reason
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {action}"
            )
        
        logger.info(f"Vendor {vendor_id} {action} by user {user_id}")
        return result
    
    def get_supported_actions(self) -> list[str]:
        return ["approve", "reject"]


class ComplaintHandler(NotificationActionHandler):
    """Handler for complaint notifications"""
    
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle complaint acknowledgment and resolution actions"""
        complaint_id = action_data.get("complaint_id")
        
        if not complaint_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Complaint ID is required"
            )
        
        if action == "acknowledge":
            # Here you would typically:
            # 1. Update complaint status to acknowledged
            # 2. Assign to support staff
            # 3. Set response deadline
            result = {
                "success": True,
                "message": f"Complaint {complaint_id} acknowledged",
                "complaint_id": complaint_id,
                "status": "acknowledged",
                "acknowledged_by": str(user_id)
            }
            
        elif action == "resolve":
            resolution = action_data.get("resolution", "Issue resolved")
            
            # Here you would typically:
            # 1. Update complaint status to resolved
            # 2. Send resolution notification to complainant
            # 3. Log resolution details
            result = {
                "success": True,
                "message": f"Complaint {complaint_id} resolved",
                "complaint_id": complaint_id,
                "status": "resolved",
                "resolved_by": str(user_id),
                "resolution": resolution
            }
            
        elif action == "escalate":
            escalation_reason = action_data.get("escalation_reason", "Requires higher level attention")
            
            # Here you would typically:
            # 1. Update complaint status to escalated
            # 2. Notify management
            # 3. Update priority
            result = {
                "success": True,
                "message": f"Complaint {complaint_id} escalated",
                "complaint_id": complaint_id,
                "status": "escalated",
                "escalated_by": str(user_id),
                "escalation_reason": escalation_reason
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {action}"
            )
        
        logger.info(f"Complaint {complaint_id} {action} by user {user_id}")
        return result
    
    def get_supported_actions(self) -> list[str]:
        return ["acknowledge", "resolve", "escalate"]


class PaymentHandler(NotificationActionHandler):
    """Handler for payment notifications"""
    
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle payment processing actions"""
        payment_id = action_data.get("payment_id")
        
        if not payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment ID is required"
            )
        
        if action == "process":
            # Here you would typically:
            # 1. Process the payment
            # 2. Update payment status
            # 3. Send receipt
            result = {
                "success": True,
                "message": f"Payment {payment_id} processed successfully",
                "payment_id": payment_id,
                "status": "processed",
                "processed_by": str(user_id)
            }
            
        elif action == "verify":
            verification_status = action_data.get("verification_status", "verified")
            
            # Here you would typically:
            # 1. Verify payment details
            # 2. Update verification status
            result = {
                "success": True,
                "message": f"Payment {payment_id} verified",
                "payment_id": payment_id,
                "verification_status": verification_status,
                "verified_by": str(user_id)
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {action}"
            )
        
        logger.info(f"Payment {payment_id} {action} by user {user_id}")
        return result
    
    def get_supported_actions(self) -> list[str]:
        return ["process", "verify"]


class UserCreatedHandler(NotificationActionHandler):
    """Handler for user creation notifications"""
    
    async def handle(self, action: str, action_data: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Handle user creation actions (like viewing user details)"""
        user_id_from_action = action_data.get("user_id")
        redirect_url = action_data.get("redirect_url")
        
        if action == "view_user":
            if not user_id_from_action:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User ID is required"
                )
            
            result = {
                "success": True,
                "message": f"Redirecting to user details for user {user_id_from_action}",
                "user_id": user_id_from_action,
                "redirect_url": redirect_url or f"/users/view-user/{user_id_from_action}",
                "action": "view_user"
            }
            
        elif action == "dismiss":
            result = {
                "success": True,
                "message": "User creation notification dismissed",
                "action": "dismiss"
            }
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {action}"
            )
        
        logger.info(f"User creation notification {action} by user {user_id}")
        return result
    
    def get_supported_actions(self) -> list[str]:
        return ["view_user", "dismiss"]


class NotificationActionManager:
    """Manager for notification action handlers"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.handlers: Dict[str, NotificationActionHandler] = {
            "trip_approval": TripApprovalHandler(session),
            "vendor_approval": VendorApprovalHandler(session),
            "complaint": ComplaintHandler(session),
            "payment": PaymentHandler(session),
            "user_created": UserCreatedHandler(session),
        }
    
    def register_handler(self, notification_type: str, handler: NotificationActionHandler):
        """Register a new action handler"""
        self.handlers[notification_type] = handler
        logger.info(f"Registered handler for {notification_type}")
    
    async def handle_action(
        self, 
        notification_type: str, 
        action: str, 
        action_data: Dict[str, Any], 
        user_id: UUID
    ) -> Dict[str, Any]:
        """Handle a notification action"""
        handler = self.handlers.get(notification_type)
        
        if not handler:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No handler found for notification type: {notification_type}"
            )
        
        if action not in handler.get_supported_actions():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action '{action}' not supported for {notification_type}"
            )
        
        try:
            return await handler.handle(action, action_data, user_id)
        except Exception as e:
            logger.error(f"Error handling action {action} for {notification_type}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process action: {str(e)}"
            )
    
    def get_supported_actions(self, notification_type: str) -> list[str]:
        """Get supported actions for a notification type"""
        handler = self.handlers.get(notification_type)
        return handler.get_supported_actions() if handler else []
    
    def get_all_supported_types(self) -> list[str]:
        """Get all supported notification types"""
        return list(self.handlers.keys())
