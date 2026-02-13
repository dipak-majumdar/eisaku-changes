from fastapi import APIRouter, Depends, Request, Query
from uuid import UUID
from typing import Optional

from api.deps import get_notification_service
from core.security import permission_required
from schemas.notifications import (
    NotificationList, 
    NotificationRead,
    NotificationCreate,
    NotificationAction,
    NotificationActionResponse,
    NotificationBulkAction,
    NotificationCount
)
from services.notifications import NotificationService

router = APIRouter()

@router.get("/all", response_model=NotificationList)
@permission_required()
async def get_all_notifications(
    request: Request,
    page: int = 1,
    size: int = 20,
    unread_only: bool = False,
    action_required: Optional[bool] = None,
    notification_type: Optional[str] = None,
    service: NotificationService = Depends(get_notification_service)
):
    """Get ALL notifications (including broadcast and other users) - for admin/testing"""
    return await service.get_all_notifications(
        request, 
        page, 
        size, 
        unread_only,
        action_required,
        notification_type
    )

@router.get("/", response_model=NotificationList)
@permission_required()
async def get_notifications(
    request: Request,
    page: int = 1,
    size: int = 20,
    unread_only: bool = False,
    action_required: Optional[bool] = None,
    notification_type: Optional[str] = None,
    service: NotificationService = Depends(get_notification_service)
):
    """Get user's notifications with enhanced filtering"""
    user = request.state.user
    return await service.get_user_notifications(
        request, 
        user.id, 
        page, 
        size, 
        unread_only,
        action_required,
        notification_type
    )

@router.get("/counts", response_model=NotificationCount)
@permission_required()
async def get_notification_counts(
    request: Request,
    service: NotificationService = Depends(get_notification_service)
):
    """Get notification counts for the user"""
    user = request.state.user
    return await service.get_notification_counts(user.id)

# @router.post(
#     "/", 
#     response_model=NotificationRead,
#     summary="Create a new notification",
#     description="Create a new notification that can be targeted to specific users or broadcast to all users",
#     responses={
#         200: {
#             "description": "Notification created successfully",
#             "content": {
#                 "application/json": {
#                     "example": {
#                         "id": "123e4567-e89b-12d3-a456-426614174000",
#                         "user_id": null,
#                         "role": "admin",
#                         "notification_type": "trip_approval",
#                         "message": "Trip TRP000001 Created!",
#                         "action_required": True,
#                         "action_data": {
#                             "buttons": [
#                                 {"name": "approve", "url": "/trips/approve"},
#                                 {"name": "reject", "url": "/trips/reject"}
#                             ],
#                             "redirect_url": "/trips"
#                         },
#                         "action_deadline": "2024-01-15T10:30:00Z",
#                         "is_read": False,
#                         "read_at": None,
#                         "created_at": "2024-01-10T08:00:00Z",
#                         "updated_at": "2024-01-10T08:00:00Z"
#                     }
#                 }
#             }
#         }
#     }
# )
@router.post("/", response_model=NotificationRead)
@permission_required()
async def create_notification(
    request: Request,
    notification_data: NotificationCreate,
    service: NotificationService = Depends(get_notification_service)
):
    """Create a new notification (admin/system use)"""
    return await service.create_notification(notification_data, request)

@router.get("/{notification_id}", response_model=NotificationRead)
@permission_required()
async def get_notification(
    request: Request,
    notification_id: UUID,
    service: NotificationService = Depends(get_notification_service)
):
    """Get a specific notification"""
    user = request.state.user
    return await service.mark_as_read(request, notification_id, user.id)

@router.patch("/{notification_id}/read", response_model=NotificationRead)
@permission_required()
async def mark_notification_read(
    request: Request,
    notification_id: UUID,
    service: NotificationService = Depends(get_notification_service)
):
    """Mark notification as read"""
    user = request.state.user
    return await service.mark_as_read(request, notification_id, user.id)

@router.post("/{notification_id}/action", response_model=NotificationActionResponse)
@permission_required()
async def take_notification_action(
    request: Request,
    notification_id: UUID,
    action_data: NotificationAction,
    service: NotificationService = Depends(get_notification_service)
):
    """Take action on a notification"""
    user = request.state.user
    return await service.take_action(notification_id, action_data, request, user.id)

@router.post("/mark-all-read")
@permission_required()
async def mark_all_read(
    request: Request,
    service: NotificationService = Depends(get_notification_service)
):
    """Mark all notifications as read"""
    user = request.state.user
    return await service.mark_all_as_read(request, user.id)

@router.post("/bulk-action")
@permission_required()
async def bulk_notification_action(
    request: Request,
    bulk_action: NotificationBulkAction,
    service: NotificationService = Depends(get_notification_service)
):
    """Perform bulk action on notifications"""
    user = request.state.user
    return await service.bulk_action(
        bulk_action.notification_ids, 
        bulk_action.action, 
        request, 
        user.id
    )
