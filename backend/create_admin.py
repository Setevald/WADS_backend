#!/usr/bin/env python3
"""
Create a clean admin user for testing
"""

import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.utils.auth import get_password_hash


async def create_admin_user():
    """Create a clean admin user"""
    try:
        client = AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.database_name]
        
        email = "admin@helpdesk.com"
        password = "admin123"
        
        print(f"🔧 Creating/updating admin user: {email}")
        
        # Hash the password
        password_hash = get_password_hash(password)
        
        # Create admin user data
        admin_data = {
            "username": "admin",
            "email": email,
            "full_name": "Administrator",
            "role": "admin",
            "status": "active",
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": None,
            "phone": None,
            "department": "IT",
            "avatar_url": None
        }
        
        # Delete existing admin user if exists
        await db.users.delete_many({"email": email})
        
        # Insert new admin user
        result = await db.users.insert_one(admin_data)
        
        print(f"✅ Created admin user with ID: {result.inserted_id}")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
        print(f"🎭 Role: admin")
        
        # Verify the user was created correctly
        created_user = await db.users.find_one({"email": email})
        if created_user:
            print(f"\n✅ Verification successful:")
            print(f"  Username: {created_user.get('username')}")
            print(f"  Full Name: {created_user.get('full_name')}")
            print(f"  Role: {created_user.get('role')}")
            print(f"  Status: {created_user.get('status')}")
            print(f"  Has Password Hash: {'password_hash' in created_user}")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")


if __name__ == "__main__":
    asyncio.run(create_admin_user()) 