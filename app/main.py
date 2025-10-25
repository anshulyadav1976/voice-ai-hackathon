"""
EchoDiary - Main FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    # Startup
    print("🚀 Starting EchoDiary...")
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    # Create audio storage directory
    os.makedirs(settings.audio_storage_path, exist_ok=True)
    print(f"✅ Audio storage ready: {settings.audio_storage_path}")
    
    # TODO: Initialize Redis connection pool
    # TODO: Start background scheduler for check-ins
    
    yield
    
    # Shutdown
    print("👋 Shutting down EchoDiary...")
    # TODO: Close Redis connection
    # TODO: Stop scheduler


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Voice-first AI diary and emotional companion",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "database": "connected",
        "services": {
            "openai": bool(settings.openai_api_key),
            "redis": bool(settings.upstash_redis_url)
        }
    }


# Import and include routers
from app.routes import api, cron, layercode

# Layercode webhook - main integration point
app.include_router(layercode.router, prefix="/layercode", tags=["Layercode Webhooks"])

# Web API and scheduled tasks
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(cron.router, prefix="/cron", tags=["Scheduled Tasks"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Serve frontend pages
@app.get("/")
async def serve_index():
    """Serve main page"""
    return FileResponse("templates/index.html")


@app.get("/call.html")
async def serve_call():
    """Serve call details page"""
    return FileResponse("templates/call.html")


@app.get("/graph.html")
async def serve_graph():
    """Serve knowledge graph page"""
    return FileResponse("templates/graph.html")


@app.get("/stats.html")
async def serve_stats():
    """Serve statistics page"""
    return FileResponse("templates/stats.html")


@app.get("/talk.html")
async def serve_talk():
    """Serve web calling page"""
    return FileResponse("templates/talk.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

