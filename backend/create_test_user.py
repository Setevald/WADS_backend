#!/usr/bin/env python3
"""
Create a test user for debugging
"""

import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.utils.auth import get_password_hash


async def create_test_user():
    """Create a test user"""
    try:
        client = AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.database_name]
        
        email = "test@example.com"
        password = "test123"
        
        print(f"🔧 Creating/updating test user: {email}")
        
        # Hash the password
        password_hash = get_password_hash(password)
        
        # Create user data
        user_data = {
            "username": "testuser",
            "email": email,
            "full_name": "Test User",
            "role": "customer",
            "status": "active",
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_login": None,
            "phone": None,
            "department": None,
            "avatar_url": None
        }
        
        # Delete existing user if exists
        await db.users.delete_many({"email": email})
        
        # Insert new user
        result = await db.users.insert_one(user_data)
        
        print(f"✅ Created test user with ID: {result.inserted_id}")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
        print(f"🎭 Role: customer")
        
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
        print(f"❌ Error creating test user: {e}")


if __name__ == "__main__":
    asyncio.run(create_test_user()) 