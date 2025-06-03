#!/usr/bin/env python3
"""
Development server runner for Help Desk System Backend
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("🚀 Starting Help Desk System Backend...")
    print(f"📚 Database: {settings.database_name}")
    print(f"🌐 Server: http://{settings.host}:{settings.port}")
    print(f"📖 API Docs: http://{settings.host}:{settings.port}/api/docs")
    print("=" * 50)
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
        access_log=True
    ) 