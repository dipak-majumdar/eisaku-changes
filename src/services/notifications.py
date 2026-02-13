from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from fastapi import HTTPException, Request, status
from typing import Optional, List, Dict, Any
from schemas.notifications import (
    NotificationList, 
    NotificationRead, 
    NotificationCreate,
    NotificationAction,
    NotificationActionResponse,
    NotificationBulkAction,
    NotificationCount
)
from models.notifications import Notification as Model
from core.websocket_manager import socket_manager
from services.notification_actions import NotificationActionManager


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.action_manager = NotificationActionManager(session)
    
    async def get_all_notifications(
        self, 
        request: Request, 
        page: int = 1,
        size: int = 20,
        unread_only: bool = False,
        action_required: Optional[bool] = None,
        notification_type: Optional[str] = None
    ) -> NotificationList:
        """Get ALL notifications (including broadcast and other users) - for admin/testing"""
        
        # Build query - NO user_id filter to get all notifications
        query = select(Model).where(Model.is_active == True)
        
        if unread_only:
            query = query.where(Model.is_read == False)
        
        if action_required is not None:
            query = query.where(Model.action_required == action_required)
        
        if notification_type:
            query = query.where(Model.notification_type == notification_type)
        
        # Order by newest first
        query = query.order_by(Model.created_at.desc())
        
        # Get total count
        total_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(total_query)
        total = total_result.scalar()
        
        # Get unread count
        unread_query = select(func.count()).where(
            Model.is_read == False,
            Model.is_active == True
        )
        unread_result = await self.session.execute(unread_query)
        unread_count = unread_result.scalar()
        
        # Get pending actions count
        pending_actions_query = select(func.count()).where(
            Model.action_required == True,
            Model.is_read == False,
            Model.is_active == True
        )
        pending_actions_result = await self.session.execute(pending_actions_query)
        pending_actions_count = pending_actions_result.scalar()
        
        # Paginate
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await self.session.execute(query)
        results = result.scalars().unique().all()
        
        return NotificationList(
            total=total,
            unread_count=unread_count,
            results=[NotificationRead.model_validate(result) for result in results]
        )
    
    async def get_user_notifications(
        self, 
        request: Request, 
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        unread_only: bool = False,
        action_required: Optional[bool] = None,
        notification_type: Optional[str] = None
    ) -> NotificationList:
        """Get notifications for a user with enhanced filtering"""
        
        # Build query
        query = select(Model).where(Model.user_id == user_id, Model.is_active == True)
        
        if unread_only:
            query = query.where(Model.is_read == False)
        
        if action_required is not None:
            query = query.where(Model.action_required == action_required)
        
        if notification_type:
            query = query.where(Model.notification_type == notification_type)
        
        # Order by newest first
        query = query.order_by(Model.created_at.desc())
        
        # Get total count
        total_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(total_query)
        total = total_result.scalar()
        
        # Get unread count
        unread_query = select(func.count()).where(
            Model.user_id == user_id,
            Model.is_read == False,
            Model.is_active == True
        )
        unread_result = await self.session.execute(unread_query)
        unread_count = unread_result.scalar()
        
        # Get pending actions count
        pending_actions_query = select(func.count()).where(
            Model.user_id == user_id,
            Model.action_required == True,
            Model.is_read == False,
            Model.is_active == True
        )
        pending_actions_result = await self.session.execute(pending_actions_query)
        pending_actions_count = pending_actions_result.scalar()
        
        # Paginate
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        result = await self.session.execute(query)
        results = result.scalars().unique().all()
        
        return NotificationList(
            total=total,
            unread_count=unread_count,
            results=[NotificationRead.model_validate(result) for result in results]
        )
    
    async def get_notification_counts(self, user_id: UUID) -> NotificationCount:
        """Get notification counts for a user"""
        total_query = select(func.count()).where(
            Model.user_id == user_id,
            Model.is_active == True
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar()
        
        unread_query = select(func.count()).where(
            Model.user_id == user_id,
            Model.is_read == False,
            Model.is_active == True
        )
        unread_result = await self.session.execute(unread_query)
        unread = unread_result.scalar()
        
        pending_actions_query = select(func.count()).where(
            Model.user_id == user_id,
            Model.action_required == True,
            Model.action_taken.is_(None),
            Model.is_active == True
        )
        pending_actions_result = await self.session.execute(pending_actions_query)
        pending_actions = pending_actions_result.scalar()
        
        return NotificationCount(
            total=total,
            unread=unread,
            pending_actions=pending_actions
        )
    
    async def create_notification(self, notification_data: NotificationCreate, request: Request) -> NotificationRead:
        """Create a new notification"""
        import json
        
        # Convert action_data dict to JSON string if provided
        action_data_json = None
        if notification_data.action_data:
            action_data_json = json.dumps(notification_data.action_data)

        # Convert user_ids list to JSON string if provided
        user_ids_json = None
        if notification_data.user_ids:
            user_ids_json = json.dumps(notification_data.user_ids)

        db_obj = Model(
            user_ids=user_ids_json or None,
            role=notification_data.role or None,
            notification_type=notification_data.notification_type,
            message=notification_data.message,
            action_required=notification_data.action_required,
            action_data=action_data_json or None,
            action_deadline=notification_data.action_deadline or None,
        )
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        
        # Convert to read schema
        notification_read = NotificationRead.model_validate(db_obj)
        
        # Send real-time notification via existing WebSocket manager
        notification_dict = {
            "notification_type": db_obj.notification_type,
            "user_ids": db_obj.user_ids,  # Already JSON string from database
            "role": db_obj.role,
            "notification_id": str(db_obj.id),
            "message": db_obj.message,
            "action_required": db_obj.action_required,
            "action_data": db_obj.action_data,
            "created_at": db_obj.created_at.isoformat()
        }
        
        # ✅ AWAIT the WebSocket send to prevent race conditions
        try:
            print(f"🔍 Active WebSocket connections: {len(socket_manager.active_connections)}")
            print(f"🔍 Sending notification: {notification_dict.get('notification_type')}")
            
            # CRITICAL FIX: Await instead of fire-and-forget
            await socket_manager.send_notification_to_all(notification_dict, None)
            print("✅ Notification sent to all connections")
        except Exception as e:
            print(f"❌ Error in WebSocket send: {str(e)}")
            # Log but don't fail the request
            pass
        
        return notification_read
    
    async def mark_as_read(self, request: Request, notification_id: UUID, user_id: UUID):
        """Mark notification as read"""
        result = await self.session.execute(
            select(Model).where(Model.id == notification_id, Model.is_active == True)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Verify ownership
        if notification.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(notification)
        
        return NotificationRead.model_validate(notification)
    
    async def mark_all_as_read(self, request: Request, user_id: UUID):
        """Mark all notifications as read for a user"""
        stmt = (
            update(Model)
            .where(Model.user_id == user_id, Model.is_read == False, Model.is_active == True)
            .values(is_read=True, read_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.commit()
        
        return {"message": "All notifications marked as read"}
    
    async def take_action(self, notification_id: UUID, action_data: NotificationAction, request: Request, user_id: UUID) -> NotificationActionResponse:
        """Take action on a notification"""
        result = await self.session.execute(
            select(Model).where(Model.id == notification_id, Model.is_active == True)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Verify ownership
        if notification.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        if not notification.action_required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This notification does not require action"
            )
        
        # Check if action deadline has passed
        if notification.action_deadline and datetime.utcnow() > notification.action_deadline:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Action deadline has passed"
            )
        
        # Parse action_data from JSON string if it exists
        parsed_action_data = {}
        if notification.action_data:
            try:
                import json
                parsed_action_data = json.loads(notification.action_data)
            except json.JSONDecodeError:
                parsed_action_data = {}
        
        # Merge with additional action data from request
        if action_data.action_data:
            parsed_action_data.update(action_data.action_data)
        
        try:
            # Handle the action using the action manager
            action_result = await self.action_manager.handle_action(
                notification.notification_type,
                action_data.action,
                parsed_action_data,
                user_id
            )
            
            # Update the notification
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(notification)
            
            return NotificationActionResponse(
                success=True,
                message=f"Action '{action_data.action}' taken successfully",
                data={
                    "notification_id": str(notification_id),
                    "action_taken": action_data.action,
                    "action_taken_at": datetime.utcnow().isoformat(),
                    "action_result": action_result
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process action: {str(e)}"
            )
    
    async def bulk_action(self, notification_ids: List[UUID], action: str, request: Request, user_id: UUID) -> Dict[str, Any]:
        """Perform bulk action on notifications"""
        if not notification_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notification IDs list cannot be empty"
            )
        
        # Check which notifications exist and belong to user
        result = await self.session.execute(
            select(Model).where(
                Model.id.in_(notification_ids),
                Model.user_id == user_id,
                Model.is_active == True
            )
        )
        notifications = result.scalars().all()
        
        existing_ids = {notification.id for notification in notifications}
        
        # Find missing IDs
        missing_ids = set(notification_ids) - existing_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notifications not found: {list(missing_ids)}"
            )
        
        # Perform bulk action
        if action == "mark_read":
            for notification in notifications:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
            message = f"Marked {len(notifications)} notifications as read"
            
        elif action == "delete":
            for notification in notifications:
                notification.is_active = False
            message = f"Deleted {len(notifications)} notifications"
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bulk action: {action}"
            )
        
        await self.session.commit()
        
        return {
            "message": message,
            "affected_count": len(notifications),
            "action": action
        }
