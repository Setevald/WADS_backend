#!/usr/bin/env python3
"""
Script to activate user accounts by setting their status to 'active'
"""

import asyncio
import sys
from app.database.connection import init_database, get_database
from app.config import settings


async def activate_user(email: str):
    """Activate a user account by email"""
    try:
        # Initialize database connection
        await init_database()
        db = get_database()
        
        print(f"🔍 Looking for user with email: {email}")
        
        # Find the user
        user = await db.users.find_one({"email": email})
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return False
        
        print(f"✅ Found user: {user['username']} ({user['full_name']})")
        print(f"📊 Current status: {user.get('status', 'Not set')}")
        print(f"👤 Role: {user.get('role', 'Not set')}")
        
        # Update user status to active
        result = await db.users.update_one(
            {"email": email},
            {"$set": {"status": "active"}}
        )
        
        if result.modified_count > 0:
            print(f"✅ Successfully activated user account!")
            
            # Verify the update
            updated_user = await db.users.find_one({"email": email})
            print(f"📊 New status: {updated_user.get('status')}")
            return True
        else:
            print(f"⚠️  No changes made (user might already be active)")
            return True
            
    except Exception as e:
        print(f"❌ Error activating user: {e}")
        return False


async def list_all_users():
    """List all users and their status"""
    try:
        await init_database()
        db = get_database()
        
        print("📋 All users in the database:")
        print("-" * 80)
        
        users = await db.users.find({}).to_list(length=None)
        
        if not users:
            print("No users found in the database")
            return
        
        for user in users:
            status = user.get('status', 'Not set')
            role = user.get('role', 'Not set')
            print(f"📧 {user['email']:<30} | 👤 {user['username']:<20} | 🎭 {role:<10} | 📊 {status}")
        
        print("-" * 80)
        print(f"Total users: {len(users)}")
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} <email>           - Activate specific user")
        print(f"  python {sys.argv[0]} --list           - List all users")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "--list":
        await list_all_users()
    else:
        email = command
        success = await activate_user(email)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 