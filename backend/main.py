"""
Help Desk System Backend
FastAPI application with MongoDB integration
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database.connection import init_database, close_database
from app.routes import auth, tickets, users, chat, notifications, admin
from app.websocket import routes as websocket_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events"""
    # Startup
    await init_database()
    print("🚀 Help Desk API started successfully!")
    print(f"📚 Database: {settings.database_name}")
    print(f"🌐 Server: http://{settings.host}:{settings.port}")
    
    yield
    
    # Shutdown
    await close_database()
    print("👋 Help Desk API shutdown complete!")

# Initialize FastAPI app
app = FastAPI(
    title="Help Desk System API",
    description="A comprehensive help desk system with ticket management, real-time chat, and admin dashboard",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    redirect_slashes=True  # Enable automatic redirects for trailing slashes
)

# Configure CORS with more explicit settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://wads-fp-beta.vercel.app",  # your Vercel frontend
        "http://localhost:3000",            # local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["Tickets"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(websocket_routes.router, prefix="/ws", tags=["WebSocket"])

# Add specific redirect for notifications without trailing slash
@app.get("/api/notifications")
async def redirect_notifications():
    """Redirect notifications without slash to proper endpoint"""
    return RedirectResponse(url="/api/notifications/", status_code=307)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Help Desk System API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "status": "running"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle OPTIONS requests for CORS preflight"""
    return {"message": "OK"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.debug,
        log_level="info"
    ) 