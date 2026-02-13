#!/usr/bin/env python3
"""
WebSocket Connection Test Script

Tests multiple concurrent WebSocket connections to verify notification delivery.
"""
import asyncio
import websockets
import json
import sys
from datetime import datetime

# Configuration
WS_URL = "ws://localhost:9000/api/ws"
TOKENS = []  # Add your JWT tokens here

async def connect_user(user_id: int, token: str):
    """Connect a single user and listen for notifications"""
    uri = f"{WS_URL}?token={token}"
    notifications_received = []
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ User {user_id} connected")
            
            # Receive welcome message
            welcome = await websocket.recv()
            print(f"👤 User {user_id}: {welcome}")
            
            # Listen for notifications
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "ping":
                        # Respond to server ping
                        await websocket.send(json.dumps({"type": "pong"}))
                        print(f"🏓 User {user_id}: Pong sent")
                    else:
                        # Notification received
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"📨 [{timestamp}] User {user_id} received: {data.get('notification_type', 'unknown')} - {data.get('message', '')[:50]}")
                        notifications_received.append(data)
                
                except asyncio.TimeoutError:
                    print(f"⏱️ User {user_id}: No messages for 60s, still connected")
                    continue
    
    except websockets.exceptions.ConnectionClosed:
        print(f"❌ User {user_id} disconnected")
    except Exception as e:
        print(f"❌ User {user_id} error: {str(e)}")
    
    return notifications_received

async def main():
    """Run multiple concurrent connections"""
    if not TOKENS:
        print("❌ Please add JWT tokens to the TOKENS list in the script")
        print("   Get tokens from your /auth/login endpoint")
        sys.exit(1)
    
    print(f"🚀 Starting {len(TOKENS)} concurrent WebSocket connections...")
    print(f"🔗 Connecting to: {WS_URL}")
    print("-" * 60)
    
    # Create tasks for all users
    tasks = [
        connect_user(i + 1, token)
        for i, token in enumerate(TOKENS)
    ]
    
    # Run all connections concurrently
    try:
        results = await asyncio.gather(*tasks)
        
        print("\n" + "=" * 60)
        print("📊 Test Results:")
        for i, notifications in enumerate(results):
            print(f"   User {i + 1}: {len(notifications)} notifications received")
        print("=" * 60)
    
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║        WebSocket Multi-User Connection Test             ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())
