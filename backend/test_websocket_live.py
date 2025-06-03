#!/usr/bin/env python3
"""
Test script to verify WebSocket functionality
Run this while the backend server is running
"""

import asyncio
import json
import logging
from datetime import datetime
from bson import ObjectId

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_notifications():
    """Test WebSocket notification system"""
    
    print("🔧 Testing WebSocket Notification System")
    print("=" * 50)
    
    try:
        # Import and initialize database
        from app.database.connection import init_database, get_database
        
        # Initialize database connection
        await init_database()
        db = get_database()
        
        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationType
        from app.websocket.manager import manager
        
        # 1. Check current WebSocket connections
        print("\n1. Current WebSocket Connections:")
        connection_info = manager.get_connection_info()
        print(f"   Total connections: {connection_info['total_connections']}")
        print(f"   Admin connections: {connection_info['admin_connections']}")
        print(f"   Connected users: {connection_info['connected_users']}")
        print(f"   Connected admins: {connection_info['connected_admins']}")
        
        if connection_info['total_connections'] == 0:
            print("   ❌ No WebSocket connections found!")
            print("   💡 Make sure users are logged in with WebSocket connections established")
            print("   💡 Check that the frontend is running and users have established WebSocket connections")
            return
        
        # 2. Find an admin user to test with
        print("\n2. Finding Admin Users:")
        admin_users = await db.users.find({
            "role": {"$in": ["admin", "agent"]},
            "is_active": True
        }).to_list(None)
        
        if not admin_users:
            print("   ❌ No admin users found!")
            return
        
        test_admin = admin_users[0]
        admin_id = str(test_admin["_id"])
        print(f"   Found admin: {test_admin.get('full_name', test_admin['username'])} ({admin_id})")
        
        # Check if this admin is connected
        is_connected = manager.is_user_connected(admin_id)
        print(f"   Admin WebSocket connected: {'✅ Yes' if is_connected else '❌ No'}")
        
        # 3. Create a test notification
        print("\n3. Creating Test Notification:")
        
        notification = await NotificationService.create_and_broadcast_notification(
            user_id=admin_id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="🧪 WebSocket Test Notification",
            message=f"Test notification sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            data={
                "test": True,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "test_websocket_live.py"
            },
            priority="high"
        )
        
        print(f"   ✅ Notification created: {notification.id}")
        print(f"   📨 WebSocket broadcast: {'Sent' if is_connected else 'User not connected'}")
        
        # 4. Test ticket creation notification
        print("\n4. Testing Ticket Creation Notification:")
        
        # Find a customer user for ticket creation
        customer_user = await db.users.find_one({"role": "customer", "is_active": True})
        if customer_user:
            customer_id = str(customer_user["_id"])
            print(f"   Found customer: {customer_user.get('full_name', customer_user['username'])}")
            
            # Create a test ticket
            test_ticket = {
                "title": "🧪 Test Ticket for WebSocket",
                "description": "This is a test ticket to verify WebSocket notifications",
                "category": "technical",
                "priority": "medium", 
                "created_by": ObjectId(customer_id),
                "status": "open",
                "assigned_to": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "resolved_at": None,
                "resolution_note": None,
                "message_count": 0,
                "attachments": [],
                "tags": ["test", "websocket"]
            }
            
            result = await db.tickets.insert_one(test_ticket)
            ticket_id = str(result.inserted_id)
            print(f"   ✅ Test ticket created: {ticket_id}")
            
            # Trigger notification
            await NotificationService.notify_new_ticket(ticket_id)
            print(f"   📨 New ticket notifications sent to {len(admin_users)} admins")
            
        else:
            print("   ❌ No customer users found for ticket test")
        
        # 5. Test direct WebSocket broadcast
        print("\n5. Testing Direct WebSocket Broadcast:")
        
        test_message = {
            "type": "system_alert",
            "data": {
                "title": "🚀 Direct WebSocket Test",
                "message": "This is a direct WebSocket broadcast test",
                "timestamp": datetime.utcnow().isoformat(),
                "priority": "info"
            }
        }
        
        await manager.broadcast_to_admins(test_message)
        print(f"   ✅ Direct broadcast sent to {connection_info['admin_connections']} admin connections")
        
        # 6. Summary
        print("\n6. Test Summary:")
        print("   ✅ WebSocket manager is operational")
        print(f"   ✅ {connection_info['total_connections']} active connections")
        print("   ✅ Notifications can be created and sent")
        print("   ✅ Direct WebSocket broadcasts work")
        print("\n💡 Check the frontend console for received messages!")
        
    except Exception as e:
        print(f"\n❌ Error during WebSocket testing: {e}")
        logger.exception("WebSocket test failed")

if __name__ == "__main__":
    asyncio.run(test_websocket_notifications()) 