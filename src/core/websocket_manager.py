# core/websocket_manager.py
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session
from fastapi import WebSocket
from uuid import UUID
import json
import logging
import asyncio

from models.notifications import Notification

logger = logging.getLogger(__name__)

class ConnectionInfo:
    """Store metadata about a WebSocket connection"""
    def __init__(self, websocket: WebSocket, user_email: str, user_id: Optional[UUID] = None):
        self.websocket = websocket
        self.user_email = user_email
        self.user_id = user_id
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
    
    def __repr__(self):
        return f"<Connection: {self.user_email} @ {self.connected_at}>"

class ConnectionManager:
    def __init__(self):
        # Store connections with metadata
        self.active_connections: List[ConnectionInfo] = []
        # Store user_id -> connections mapping for targeted notifications
        self.user_rooms: Dict[str, List[ConnectionInfo]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_email: str, user_id: Optional[UUID] = None):
        """
        Store new connection with metadata (don't accept here - already accepted in endpoint)
        """
        async with self._lock:
            conn_info = ConnectionInfo(websocket, user_email, user_id)
            self.active_connections.append(conn_info)
            
            # Add to user room if user_id is provided
            if user_id:
                user_id_str = str(user_id)
                if user_id_str not in self.user_rooms:
                    self.user_rooms[user_id_str] = []
                self.user_rooms[user_id_str].append(conn_info)
                logger.info(f"✅ New connection: {user_email} (user_id: {user_id_str}, Total: {len(self.active_connections)})")
                print(f"✅ Connected: {user_email} (Room: {user_id_str}) | Total: {len(self.active_connections)}")
            else:
                logger.info(f"✅ New connection: {user_email} (Total: {len(self.active_connections)})")
                print(f"✅ Connected: {user_email} | Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove connection"""
        async with self._lock:
            for conn_info in self.active_connections:
                if conn_info.websocket == websocket:
                    self.active_connections.remove(conn_info)
                    
                    # Remove from user room if exists
                    if conn_info.user_id:
                        user_id_str = str(conn_info.user_id)
                        if user_id_str in self.user_rooms:
                            self.user_rooms[user_id_str] = [
                                c for c in self.user_rooms[user_id_str] 
                                if c.websocket != websocket
                            ]
                            # Clean up empty rooms
                            if not self.user_rooms[user_id_str]:
                                del self.user_rooms[user_id_str]
                    
                    logger.info(f"❌ Disconnected: {conn_info.user_email} (Remaining: {len(self.active_connections)})")
                    print(f"❌ Disconnected: {conn_info.user_email} | Remaining: {len(self.active_connections)}")
                    break
    
    async def update_ping(self, websocket: WebSocket):
        """Update last ping time for a connection"""
        for conn_info in self.active_connections:
            if conn_info.websocket == websocket:
                conn_info.last_ping = datetime.utcnow()
                break
    
    async def send_notification_to_all(self, notification: dict, db_session: Session = None):
        """Send notification to all connected clients with timeout protection"""
        
        # ✅ Save to database first (without user_id for broadcast notifications)
        if db_session:
            try:
                db_notification = Notification(
                    notification_type=notification.get('notification_type', 'general'),
                    user_id=notification.get('user_id'),  # sent to whom
                    role=notification.get('role'),
                    message=notification.get('message', ''),
                    action_required=notification.get('action_required', False),
                    action_data=json.dumps(notification.get('action_data')) if notification.get('action_data') else None,
                    action_deadline=datetime.fromisoformat(notification['action_deadline']) if notification.get('action_deadline') else None,
                    is_read=False
                )
                
                db_session.add(db_notification)
                db_session.commit()
                db_session.refresh(db_notification)
                
                # Add notification ID to the message
                notification['notification_id'] = str(db_notification.id)
                
                logger.info(f"💾 Broadcast notification saved to DB: {db_notification.id}")
            except Exception as e:
                logger.error(f"❌ Error saving broadcast notification to DB: {str(e)}")
                db_session.rollback()
        
        # Get snapshot of connections to avoid modification during iteration
        connections_snapshot = list(self.active_connections)
        
        print(f"🔍 Attempting to send to {len(connections_snapshot)} connections")
        print(f"🔍 Notification: {notification.get('notification_type')} - {notification.get('message', '')[:50]}")
        
        # Send to all connections CONCURRENTLY with timeout
        async def send_to_connection(conn_info: ConnectionInfo, index: int) -> Tuple[bool, Optional[str]]:
            """Send to a single connection with timeout"""
            try:
                # 5 second timeout per connection
                await asyncio.wait_for(
                    conn_info.websocket.send_json(notification),
                    timeout=5.0
                )
                logger.info(f"📨 Sent to {conn_info.user_email}")
                print(f"✅ Sent to {conn_info.user_email} (connection {index+1})")
                return True, None
            except asyncio.TimeoutError:
                error_msg = f"Timeout sending to {conn_info.user_email}"
                logger.error(f"⏱️ {error_msg}")
                print(f"⏱️ {error_msg}")
                return False, error_msg
            except Exception as e:
                error_msg = f"Error sending to {conn_info.user_email}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                print(f"❌ {error_msg}")
                return False, error_msg
        
        # Send to all connections concurrently
        tasks = [
            send_to_connection(conn_info, i) 
            for i, conn_info in enumerate(connections_snapshot)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clean up failed connections
        failed_connections = []
        for i, (conn_info, result) in enumerate(zip(connections_snapshot, results)):
            if isinstance(result, Exception) or (isinstance(result, tuple) and not result[0]):
                failed_connections.append(conn_info.websocket)
        
        # Remove failed connections
        for websocket in failed_connections:
            await self.disconnect(websocket)
        
        success_count = sum(1 for r in results if isinstance(r, tuple) and r[0])
        print(f"📊 Notification sent: {success_count}/{len(connections_snapshot)} successful")
    
    async def send_personal_message(self, message: dict):
        """Send a message to all connected clients (without saving to DB)"""
        connections_snapshot = list(self.active_connections)
        
        async def send_to_connection(conn_info: ConnectionInfo):
            try:
                await asyncio.wait_for(
                    conn_info.websocket.send_json(message),
                    timeout=5.0
                )
                logger.info(f"📨 Sent message to {conn_info.user_email}")
                return True, None
            except Exception as e:
                logger.error(f"❌ Error sending to {conn_info.user_email}: {e}")
                return False, conn_info.websocket
        
        tasks = [send_to_connection(conn_info) for conn_info in connections_snapshot]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clean up failed connections
        for result in results:
            if isinstance(result, tuple) and not result[0] and result[1]:
                await self.disconnect(result[1])
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users"""
        await self.send_personal_message(message)
    
    async def send_to_users(self, user_ids: List[str], notification: dict, db_session: Session = None):
        """
        Send notification to specific users only (targeted delivery)
        
        Args:
            user_ids: List of user IDs to send notification to
            notification: Notification data to send
            db_session: Optional database session for saving notification
        """
        # Save to database if session provided
        if db_session:
            try:
                db_notification = Notification(
                    notification_type=notification.get('notification_type', 'general'),
                    user_id=notification.get('user_id'),
                    role=notification.get('role'),
                    message=notification.get('message', ''),
                    action_required=notification.get('action_required', False),
                    action_data=json.dumps(notification.get('action_data')) if notification.get('action_data') else None,
                    action_deadline=datetime.fromisoformat(notification['action_deadline']) if notification.get('action_deadline') else None,
                    is_read=False
                )
                
                db_session.add(db_notification)
                db_session.commit()
                db_session.refresh(db_notification)
                
                notification['notification_id'] = str(db_notification.id)
                logger.info(f"💾 Targeted notification saved to DB: {db_notification.id}")
            except Exception as e:
                logger.error(f"❌ Error saving targeted notification to DB: {str(e)}")
                db_session.rollback()
        
        print(f"🎯 Sending targeted notification to {len(user_ids)} users")
        print(f"🎯 Target users: {user_ids}")
        print(f"🎯 Notification: {notification.get('notification_type')} - {notification.get('message', '')[:50]}")
        
        sent_count = 0
        failed_connections = []
        
        for user_id in user_ids:
            user_id_str = str(user_id)
            
            if user_id_str not in self.user_rooms:
                print(f"⚠️ User {user_id_str} not connected (no active WebSocket)")
                continue
            
            # Send to all connections for this user (multi-device support)
            user_connections = self.user_rooms[user_id_str]
            print(f"📱 User {user_id_str} has {len(user_connections)} active connection(s)")
            
            for conn_info in user_connections:
                try:
                    await asyncio.wait_for(
                        conn_info.websocket.send_json(notification),
                        timeout=5.0
                    )
                    logger.info(f"📨 Sent to user {user_id_str} ({conn_info.user_email})")
                    print(f"✅ Sent to {conn_info.user_email}")
                    sent_count += 1
                except asyncio.TimeoutError:
                    logger.error(f"⏱️ Timeout sending to user {user_id_str}")
                    print(f"⏱️ Timeout sending to {conn_info.user_email}")
                    failed_connections.append(conn_info.websocket)
                except Exception as e:
                    logger.error(f"❌ Error sending to user {user_id_str}: {str(e)}")
                    print(f"❌ Error sending to {conn_info.user_email}: {str(e)}")
                    failed_connections.append(conn_info.websocket)
        
        # Clean up failed connections
        for websocket in failed_connections:
            await self.disconnect(websocket)
        
        print(f"📊 Targeted notification: {sent_count} sent, {len(failed_connections)} failed")
    
    def get_connection_stats(self) -> dict:
        """Get statistics about active connections"""
        return {
            "total_connections": len(self.active_connections),
            "connections": [
                {
                    "user_email": conn.user_email,
                    "user_id": str(conn.user_id) if conn.user_id else None,
                    "connected_at": conn.connected_at.isoformat(),
                    "last_ping": conn.last_ping.isoformat()
                }
                for conn in self.active_connections
            ]
        }

# Global instance
socket_manager = ConnectionManager()
