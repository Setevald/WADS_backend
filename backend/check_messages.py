#!/usr/bin/env python3
"""
Script to check message structure in the database
"""

import asyncio
from app.database.connection import init_database, get_database
from bson import ObjectId


async def check_message_structure():
    """Check the structure of messages in the database"""
    try:
        await init_database()
        db = get_database()
        
        print("🔍 Checking message structure...")
        
        # Get a sample message
        message = await db.messages.find_one()
        if message:
            print("\n📄 Sample message structure:")
            for key, value in message.items():
                print(f"  {key}: {type(value).__name__} = {value}")
        else:
            print("❌ No messages found in database")
        
        # Get user information for comparison
        print("\n👤 Checking user structure...")
        user = await db.users.find_one()
        if user:
            print("\n📄 Sample user structure:")
            for key, value in user.items():
                if key != 'password_hash':  # Don't print password hash
                    print(f"  {key}: {type(value).__name__} = {value}")
        else:
            print("❌ No users found in database")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(check_message_structure()) 