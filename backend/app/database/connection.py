"""
Database connection module
Handles MongoDB connection using Motor (async MongoDB driver)
"""

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ServerSelectionTimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.client: Optional["AsyncIOMotorClient"] = None
        self.database: Optional["AsyncIOMotorDatabase"] = None
        
    async def connect(self) -> None:
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(
                settings.mongodb_url,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=10
            )
            
            # Test the connection
            await self.client.admin.command('ismaster')
            self.database = self.client[settings.database_name]
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info(f"✅ Connected to MongoDB database: {settings.database_name}")
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("📤 Disconnected from MongoDB")
    
    async def _create_indexes(self) -> None:
        """Create database indexes for optimal performance"""
        try:
            # Users collection indexes
            await self.database.users.create_index("email", unique=True)
            await self.database.users.create_index("username", unique=True)
            await self.database.users.create_index([("created_at", -1)])
            
            # Tickets collection indexes
            await self.database.tickets.create_index([("created_at", -1)])
            await self.database.tickets.create_index("status")
            await self.database.tickets.create_index("priority")
            await self.database.tickets.create_index("assigned_to")
            await self.database.tickets.create_index("created_by")
            await self.database.tickets.create_index([("title", "text"), ("description", "text")])
            
            # Messages collection indexes
            await self.database.messages.create_index([("created_at", -1)])
            await self.database.messages.create_index("ticket_id")
            await self.database.messages.create_index("sender_id")
            
            # Notifications collection indexes
            await self.database.notifications.create_index([("created_at", -1)])
            await self.database.notifications.create_index("user_id")
            await self.database.notifications.create_index("is_read")
            
            logger.info("📊 Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Error creating indexes: {e}")

# Create global database instance
db = Database()

async def init_database() -> None:
    """Initialize database connection"""
    await db.connect()

async def close_database() -> None:
    """Close database connection"""
    await db.disconnect()

def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    if db.database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db.database 