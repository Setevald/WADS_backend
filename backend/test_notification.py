#!/usr/bin/env python3
"""
Test script to verify notification system functionality
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database.connection import get_database
from app.services.notification_service import notification_service
from app.models.notification import NotificationType


async def test_notification_system():
    """Test the notification system"""
    print("Testing notification system...")
    
    try:
        db = get_database()
        
        # Find an admin user
        admin_user = await db.users.find_one({"role": "admin"})
        if not admin_user:
            print("No admin user found. Please create an admin user first.")
            return
        
        admin_id = str(admin_user["_id"])
        print(f"Found admin user: {admin_user.get('full_name', admin_user['username'])} ({admin_id})")
        
        # Create a test notification
        print("Creating test notification...")
        notification = await notification_service.create_and_broadcast_notification(
            user_id=admin_id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Test Notification",
            message="This is a test notification to verify the system is working",
            data={
                "test": True,
                "timestamp": datetime.utcnow().isoformat()
            },
            priority="high"
        )
        
        print(f"Test notification created successfully: {notification.id}")
        
        # Check if notification was saved to database
        saved_notification = await db.notifications.find_one({"_id": notification.id})
        if saved_notification:
            print("✓ Notification saved to database")
        else:
            print("✗ Notification NOT saved to database")
        
        # Test ticket creation notification
        print("\nTesting ticket creation notification...")
        
        # Find a customer user
        customer_user = await db.users.find_one({"role": "customer"})
        if not customer_user:
            print("No customer user found. Skipping ticket creation test.")
            return
        
        customer_id = str(customer_user["_id"])
        print(f"Found customer user: {customer_user.get('full_name', customer_user['username'])} ({customer_id})")
        
        # Create a test ticket
        from bson import ObjectId
        from app.models.ticket import TicketStatus
        
        test_ticket = {
            "title": "Test Ticket for Notification",
            "description": "This is a test ticket to verify notification system",
            "category": "general",
            "priority": "medium",
            "created_by": ObjectId(customer_id),
            "status": TicketStatus.OPEN,
            "assigned_to": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "resolved_at": None,
            "resolution_note": None,
            "message_count": 0,
            "attachments": [],
            "tags": []
        }
        
        result = await db.tickets.insert_one(test_ticket)
        ticket_id = str(result.inserted_id)
        print(f"Test ticket created: {ticket_id}")
        
        # Test the notification service
        await notification_service.notify_new_ticket(ticket_id)
        print("✓ Ticket notification sent")
        
        # Check for admin notifications
        admin_notifications = await db.notifications.find({
            "user_id": ObjectId(admin_id),
            "notification_type": "ticket_created"
        }).sort("created_at", -1).limit(1).to_list(1)
        
        if admin_notifications:
            print("✓ Admin received ticket creation notification")
            print(f"  Title: {admin_notifications[0]['title']}")
            print(f"  Message: {admin_notifications[0]['message']}")
        else:
            print("✗ Admin did NOT receive ticket creation notification")
        
        # Clean up test ticket
        await db.tickets.delete_one({"_id": ObjectId(ticket_id)})
        print(f"Test ticket {ticket_id} cleaned up")
        
        print("\nNotification system test completed!")
        
    except Exception as e:
        print(f"Error testing notification system: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_notification_system()) 