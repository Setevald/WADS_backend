#!/usr/bin/env python3
"""
Database migration script to fix invalid notification types.
This script updates notifications with legacy/mock notification types to valid enum values.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


async def fix_notification_types() -> None:
    """Fix invalid notification types in the database."""
    
    # Type mapping for fixing legacy/mock data
    type_fixes: Dict[str, str] = {
        "assignment": "ticket_assigned",
        "urgent": "system_alert", 
        "new_ticket": "ticket_created",
        "ticket_update": "ticket_status_changed"
    }
    
    # Frontend type mapping fixes
    frontend_type_mapping: Dict[str, str] = {
        "ticket_created": "new_ticket",
        "ticket_assigned": "assignment",
        "ticket_status_changed": "ticket_update", 
        "new_message": "message",
        "ticket_resolved": "ticket_resolved",
        "system_alert": "urgent",
        "reminder": "reminder"
    }
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.database_name]
        
        print("🔍 Checking for notifications with invalid types...")
        
        # Find all notifications with invalid notification_type values
        invalid_notifications = await db.notifications.find({
            "notification_type": {"$in": list(type_fixes.keys())}
        }).to_list(None)
        
        print(f"📊 Found {len(invalid_notifications)} notifications with invalid types")
        
        if not invalid_notifications:
            print("✅ No invalid notification types found. Database is clean!")
            return
        
        # Show what will be fixed
        type_counts = {}
        for notification in invalid_notifications:
            old_type = notification.get("notification_type", "unknown")
            type_counts[old_type] = type_counts.get(old_type, 0) + 1
        
        print("\n📋 Types to be fixed:")
        for old_type, count in type_counts.items():
            new_type = type_fixes.get(old_type, "system_alert")
            print(f"  {old_type} → {new_type} ({count} notifications)")
        
        # Confirm before proceeding
        response = input("\n❓ Proceed with fixing these notification types? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operation cancelled.")
            return
        
        # Fix each invalid type
        total_updated = 0
        
        for old_type, new_type in type_fixes.items():
            print(f"\n🔧 Fixing {old_type} → {new_type}...")
            
            # Update notification_type and set appropriate frontend type
            frontend_type = frontend_type_mapping.get(new_type, "system")
            
            result = await db.notifications.update_many(
                {"notification_type": old_type},
                {
                    "$set": {
                        "notification_type": new_type,
                        "type": frontend_type,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"✅ Updated {result.modified_count} notifications")
                total_updated += result.modified_count
            else:
                print(f"ℹ️  No notifications found with type '{old_type}'")
        
        # Also fix any notifications with missing or invalid frontend 'type' field
        print(f"\n🔧 Fixing missing frontend type fields...")
        
        # Find notifications without proper frontend type
        notifications_missing_type = await db.notifications.find({
            "$or": [
                {"type": {"$exists": False}},
                {"type": ""},
                {"type": None}
            ]
        }).to_list(None)
        
        for notification in notifications_missing_type:
            notification_type = notification.get("notification_type", "system_alert")
            frontend_type = frontend_type_mapping.get(notification_type, "system")
            
            await db.notifications.update_one(
                {"_id": notification["_id"]},
                {
                    "$set": {
                        "type": frontend_type,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        if notifications_missing_type:
            print(f"✅ Fixed {len(notifications_missing_type)} notifications with missing frontend types")
            total_updated += len(notifications_missing_type)
        
        print(f"\n🎉 Successfully updated {total_updated} notifications!")
        print("✅ All notification types are now valid and compatible with the enum validation.")
        
        # Verify the fix
        print("\n🔍 Verifying fix...")
        remaining_invalid = await db.notifications.find({
            "notification_type": {"$in": list(type_fixes.keys())}
        }).to_list(None)
        
        if remaining_invalid:
            print(f"⚠️  Warning: {len(remaining_invalid)} notifications still have invalid types")
        else:
            print("✅ Verification passed: No invalid notification types remain")
        
    except Exception as e:
        print(f"❌ Error fixing notification types: {e}")
        raise
    finally:
        # Close database connection
        if 'client' in locals():
            client.close()


async def main() -> None:
    """Main function to run the notification type fix."""
    print("🚀 Starting notification type migration...")
    print("=" * 60)
    
    try:
        await fix_notification_types()
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        
    except KeyboardInterrupt:
        print("\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 