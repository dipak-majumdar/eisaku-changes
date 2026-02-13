# api/routers/websocket.py
from db.session import get_session
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status, Request
from typing import Optional
from core.websocket_manager import socket_manager
from core.security import decode_access_token
from uuid import UUID
from sqlmodel import select

from models.user import User

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT access token (fallback for browsers)")
):
    """WebSocket endpoint with JWT authentication via Bearer header or query parameter"""
    session = None
    heartbeat_task = None
    
    # ACCEPT CONNECTION FIRST
    await websocket.accept()
    
    try:
        # Try to get token from Authorization header first, then query parameter
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]  # Remove "Bearer " prefix
            print(f"🔄 Using Bearer header token: {token[:50]}...")
        elif token:
            print(f"🔄 Using query parameter token: {token[:50]}...")
        else:
            print(f"❌ No token found in headers or query parameters")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Validate token and get user email
        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")  # This is email from your JWT
            
            if not sub:
                print(f"❌ No 'sub' in payload")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # ✅ Get user_id from database using email (async generator)
            session_gen = get_session()
            session = await anext(session_gen)
            
            user_stmt = select(User).where(User.email == sub)
            user_result = await session.execute(user_stmt)
            user = user_result.scalars().first()
            
            if not user:
                print(f"❌ User not found for email: {sub}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            user_id = user.id
            print(f"✅ Token verified for: {sub} (user_id: {user_id})")
            
        except Exception as e:
            print(f"❌ Token validation failed: {str(e)}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # ✅ Register connection WITH user metadata and user_id
        await socket_manager.connect(websocket, user_email=sub, user_id=user_id)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Successfully connected to WebSocket",
            "authenticated_as": sub,
            "user_id": str(user_id)
        })
        
        # Start heartbeat task to keep connection alive
        async def heartbeat():
            """Send ping every 30 seconds to detect dead connections"""
            try:
                while True:
                    await asyncio.sleep(30)
                    try:
                        await asyncio.wait_for(
                            websocket.send_json({"type": "ping"}),
                            timeout=5.0
                        )
                        await socket_manager.update_ping(websocket)
                    except:
                        # Connection is dead, break the loop
                        break
            except asyncio.CancelledError:
                pass
        
        import asyncio
        heartbeat_task = asyncio.create_task(heartbeat())
        
        # Listen for messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                await socket_manager.update_ping(websocket)
    
    except WebSocketDisconnect:
        await socket_manager.disconnect(websocket)
    
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
        await socket_manager.disconnect(websocket)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    finally:
        # Cancel heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
        # Close session if opened
        if session:
            await session.close()




# ✅ Add this HTTP endpoint (will appear in Swagger)
@router.get("/ws/info")
async def websocket_info(request: Request):
    """
    Get WebSocket connection information.
    
    Returns the WebSocket URL and instructions for connecting.
    """
    # Get the base URL from request
    base_url = str(request.base_url).replace("http://", "ws://").replace("https://", "wss://")
    
    return {
        "websocket_url": f"{base_url}api/ws",
        "authentication": "Bearer token in Authorization header",
        "example": f"Connect to: {base_url}api/ws with Authorization: Bearer YOUR_JWT_TOKEN",
        "instructions": [
            "1. Get your JWT token from /auth/login endpoint",
            "2. Use a WebSocket client (browser console, Postman, etc.)",
            "3. Set Authorization header: 'Bearer YOUR_TOKEN'",
            "4. Connect to: ws://localhost:8000/api/ws",
            "5. Send ping: {\"type\": \"ping\"}",
            "6. Receive pong: {\"type\": \"pong\"}"
        ],
        "message_types": {
            "connection": "Sent when connection is established",
            "trip_created": "Sent when a trip is created (broadcast to all)",
            "trip_assigned": "Sent when a trip is assigned (broadcast to all)",
            "ping": "Keep-alive message (client -> server)",
            "pong": "Keep-alive response (server -> client)"
        }
    }
